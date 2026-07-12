from .base import normalize_link, map_content_type
from .title_mapper import extract_title_metadata, extract_external_ids


def map_kodik_item_to_jcp_payloads(item: dict, plugin_id: int) -> list[dict]:
    """
    Converts a single Kodik dictionary into a flat list of JCP webhook payloads.
    If the item is a movie, returns a single list element.
    If the item is a series, returns multiple payloads representing individual episodes.
    """
    payloads = []
    ext_ids = extract_external_ids(item)

    if not ext_ids:
        return payloads

    title_meta = extract_title_metadata(item)
    ctype = map_content_type(item.get('type', ''))

    if ctype == 'MOVIE':
        link = normalize_link(item.get('link', ''))
        if link:
            payloads.append({
                "plugin_id": plugin_id,
                "external_ids": ext_ids,
                "title_metadata": title_meta,
                "content_type": "ENTITY_IFRAME",
                "fetch_url": link
            })

    elif ctype == 'SERIES':
        seasons = item.get('seasons', {})
        for season_num_str, season_data in seasons.items():
            try:
                s_num = int(season_num_str)
            except ValueError:
                continue

            episodes = season_data.get('episodes', {})
            for ep_num_str, ep_data in episodes.items():
                try:
                    e_num = int(ep_num_str)
                except ValueError:
                    continue

                if isinstance(ep_data, dict):
                    link = normalize_link(ep_data.get('link', ''))
                    ep_name = ep_data.get('title', '')
                else:
                    link = normalize_link(ep_data)
                    ep_name = ''

                if link:
                    payload = {
                        "plugin_id": plugin_id,
                        "external_ids": ext_ids,
                        "title_metadata": title_meta,
                        "season_number": s_num,
                        "episode_number": e_num,
                        "content_type": "EPISODE_IFRAME",
                        "fetch_url": link
                    }
                    if ep_name:
                        payload["episodes_metadata"] = [{
                            "season_number": s_num,
                            "episode_number": e_num,
                            "name": ep_name
                        }]
                    payloads.append(payload)

    return payloads
