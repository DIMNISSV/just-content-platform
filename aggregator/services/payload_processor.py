import logging

from django.core.cache import cache
from django.db.models import Q

from aggregator.models import ExternalContentRegistry
from content.models import Title, Episode, Genre
from content.tasks import download_and_save_poster

logger = logging.getLogger(__name__)


def _apply_taxonomy(title, raw_type: str, raw_genres: list):
    from taxonomy.models import RawTerm, TaxonomyItem
    terms_to_add = []
    if raw_type:
        raw_type_clean = raw_type.strip().lower()
        rt, _ = RawTerm.objects.get_or_create(
            name=raw_type_clean,
            source_field='type'
        )
        terms_to_add.append(rt)

    for g in raw_genres:
        if not g:
            continue
        g_clean = g.strip().lower()
        rt, _ = RawTerm.objects.get_or_create(
            name=g_clean,
            source_field='genre'
        )
        terms_to_add.append(rt)

    if terms_to_add:
        title.raw_terms.add(*terms_to_add)
    all_raw_terms = title.raw_terms.all()
    tax_items = list(TaxonomyItem.objects.filter(raw_mappings__raw_term__in=all_raw_terms).distinct())
    title.taxonomy_items.set(tax_items)
    type_updated = False
    has_series = any(t.slug == 'type-series' for t in tax_items)
    has_movie = any(t.slug == 'type-movie' for t in tax_items)
    if has_series and title.type != Title.Type.SERIES:
        title.type = Title.Type.SERIES
        type_updated = True
    elif has_movie and not has_series and title.type != Title.Type.MOVIE:
        title.type = Title.Type.MOVIE
        type_updated = True
    if type_updated:
        # Avoid webhook looping
        title._is_webhook_update = True
        title.save(update_fields=['type'])
    genre_tax_items = [t for t in tax_items if t.type == TaxonomyItem.TypeChoices.GENRE]
    if genre_tax_items:
        genre_objs = []
        for gt in genre_tax_items:
            g_obj, _ = Genre.objects.get_or_create(slug=gt.slug, defaults={'name': gt.name})
            genre_objs.append(g_obj)
        title.genres.set(genre_objs)


def process_plugin_payload(plugin, data: dict) -> tuple[dict, int]:
    external_ids = data.get('external_ids', {})
    if not external_ids:
        return {"error": "external_ids mapping is required"}, 400

    valid_id_fields = ['imdb_id', 'tmdb_id', 'kp_id', 'shiki_id', 'mal_id', 'mdl_id', 'wa_id']
    # Поля, которые могут дробиться по сезонам. Мы будем их склеивать через запятую.
    split_id_fields = ['shiki_id', 'mal_id', 'mdl_id', 'wa_id']

    query = Q()
    for key, val in external_ids.items():
        if key in valid_id_fields and val:
            v_str = str(val)
            if key in split_id_fields:
                q = Q(**{f"{key}__exact": v_str}) | \
                    Q(**{f"{key}__startswith": f"{v_str},"}) | \
                    Q(**{f"{key}__endswith": f",{v_str}"}) | \
                    Q(**{f"{key}__contains": f",{v_str},"})
                query |= q
            else:
                query |= Q(**{key: v_str})

    if not query:
        return {"error": "No valid external ID fields provided"}, 400

    title = Title.objects.filter(query).first()
    title_meta = data.get('title_metadata')

    if not title:
        if not plugin.allow_title_creation:
            return {"error": "Title not found and creation is disabled"}, 404
        if not title_meta:
            return {"error": "Title not found and no title_metadata provided"}, 400

        title = Title(
            type=Title.Type.MOVIE,  # Default, will be updated by taxonomy
            name=title_meta.get('name', 'Unknown'),
            original_name=title_meta.get('original_name', ''),
            description=title_meta.get('description', ''),
            release_year=title_meta.get('release_year'),
            metadata_priority_level=plugin.metadata_priority
        )
        for k, v in external_ids.items():
            if k in valid_id_fields and v:
                setattr(title, k, str(v))

        title._is_webhook_update = True
        title.save()
        _apply_taxonomy(title, title_meta.get('raw_type'), title_meta.get('raw_genres', []))
        poster_url = title_meta.get('poster_url')
        if poster_url:
            cache_key = f"poster_download_queued_{title.id}"
            if cache.get(cache_key) != poster_url:
                cache.set(cache_key, poster_url, timeout=300)
                download_and_save_poster.delay(title.id, poster_url)
    else:
        if plugin.allow_title_update and title_meta:
            updated = False
            prio = plugin.metadata_priority
            curr_prio = title.metadata_priority_level

            def try_update(field_name, new_val):
                nonlocal updated
                if not new_val:
                    return
                curr_val = getattr(title, field_name)
                if not curr_val:
                    setattr(title, field_name, new_val)
                    updated = True
                elif prio >= curr_prio and curr_val != new_val:
                    setattr(title, field_name, new_val)
                    updated = True

            try_update('name', title_meta.get('name'))
            try_update('original_name', title_meta.get('original_name'))
            try_update('description', title_meta.get('description'))
            try_update('release_year', title_meta.get('release_year'))

            for k, v in external_ids.items():
                if k in valid_id_fields and v:
                    v_str = str(v)
                    curr_val = getattr(title, k)
                    if not curr_val:
                        setattr(title, k, v_str)
                        updated = True
                    elif k in split_id_fields:
                        existing_ids = curr_val.split(',')
                        if v_str not in existing_ids:
                            new_val = f"{curr_val},{v_str}"
                            if len(new_val) <= 100:
                                setattr(title, k, new_val)
                                updated = True
                    elif prio >= curr_prio and curr_val != v_str:
                        setattr(title, k, v_str)
                        updated = True

            if updated:
                title.metadata_priority_level = max(curr_prio, prio)
                title._is_webhook_update = True
                title.save()

            if prio >= curr_prio:
                _apply_taxonomy(title, title_meta.get('raw_type'), title_meta.get('raw_genres', []))

            poster_url = title_meta.get('poster_url')
            if poster_url:
                if not title.poster or title.poster_url != poster_url:
                    cache_key = f"poster_download_queued_{title.id}"
                    if cache.get(cache_key) != poster_url:
                        cache.set(cache_key, poster_url, timeout=300)
                        download_and_save_poster.delay(title.id, poster_url)

    episodes_meta = data.get('episodes_metadata', [])
    if title.type == Title.Type.SERIES and episodes_meta:
        for ep_data in episodes_meta:
            s_num = ep_data.get('season_number')
            e_num = ep_data.get('episode_number')
            if s_num is None or e_num is None:
                continue
            ep = Episode.objects.filter(title=title, season_number=s_num, episode_number=e_num).first()
            if not ep:
                if plugin.allow_title_creation:
                    ep = Episode(
                        title=title,
                        season_number=s_num,
                        episode_number=e_num,
                        name=ep_data.get('name', ''),
                        description=ep_data.get('description', ''),
                        metadata_priority_level=plugin.metadata_priority
                    )
                    ep._is_webhook_update = True
                    ep.save()
            else:
                if plugin.allow_title_update:
                    ep_updated = False
                    prio = plugin.metadata_priority
                    curr_prio = ep.metadata_priority_level
                    ep_name = ep_data.get('name')
                    if ep_name:
                        if not ep.name:
                            ep.name = ep_name
                            ep_updated = True
                        elif prio >= curr_prio and ep.name != ep_name:
                            ep.name = ep_name
                            ep_updated = True
                    ep_desc = ep_data.get('description')
                    if ep_desc:
                        if not ep.description:
                            ep.description = ep_desc
                            ep_updated = True
                        elif prio >= curr_prio and ep.description != ep_desc:
                            ep.description = ep_desc
                            ep_updated = True
                    if ep_updated:
                        ep.metadata_priority_level = max(curr_prio, prio)
                        ep._is_webhook_update = True
                        ep.save()

    episode = None
    season_num = data.get('season_number')
    episode_num = data.get('episode_number')
    if season_num is not None and episode_num is not None:
        episode = Episode.objects.filter(title=title, season_number=season_num, episode_number=episode_num).first()
        if not episode:
            if plugin.allow_title_creation:
                episode = Episode(
                    title=title,
                    season_number=season_num,
                    episode_number=episode_num,
                    metadata_priority_level=plugin.metadata_priority
                )
                episode._is_webhook_update = True
                episode.save()
            else:
                return {"error": "Matching episode not found and creation disabled"}, 404

    content_type = data.get('content_type')
    target_asset_uuid = data.get('target_asset_uuid')
    fetch_url = data.get('fetch_url')

    if not content_type or not fetch_url:
        return {"error": "content_type and fetch_url are required"}, 400

    try:
        registry_entry, created = ExternalContentRegistry.objects.update_or_create(
            plugin=plugin,
            title=title,
            episode=episode,
            content_type=content_type,
            target_asset_uuid=target_asset_uuid if target_asset_uuid else None,
            defaults={
                'external_id': str(list(external_ids.values())[0]),
                'fetch_url': fetch_url
            }
        )
        logger.info(f"Plugin {plugin.name} registered {content_type} for {title.name}")
        return {
            "status": "success",
            "registry_id": registry_entry.id,
            "created": created
        }, 200
    except Exception as e:
        logger.error(f"Error saving registry entry: {str(e)}")
        return {"error": "Internal server error during registration"}, 500