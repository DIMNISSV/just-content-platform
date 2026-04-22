from aggregator.models import PluginProvider
from content.models import Genre, Title, Episode, TrackGroup, AdditionalTrack
from media.models import RawMediaFile, Asset, AssetVariant, TranscodingPreset
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds the database with initial test data (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing data...')
            Genre.objects.all().delete()
            Title.objects.all().delete()
            RawMediaFile.objects.all().delete()
            Asset.objects.all().delete()
            AssetVariant.objects.all().delete()
            TranscodingPreset.objects.all().delete()
            PluginProvider.objects.all().delete()
            User.objects.all().delete()

        self.stdout.write('Seeding data...')

        # 1. Create Admin
        admin_email = 'admin@jcloud.me'
        if not User.objects.filter(email=admin_email).exists():
            User.objects.create_superuser(email=admin_email, password='admin')
            self.stdout.write(self.style.SUCCESS(f'Admin created: {admin_email} / admin'))

        # 2. Create Genres
        genre_names = ['Sci-Fi', 'Drama', 'Action', 'Comedy', 'Thriller']
        genres = []
        for name in genre_names:
            genre, _ = Genre.objects.get_or_create(name=name, defaults={'slug': name.lower()})
            genres.append(genre)

        # 3. Create Titles
        movie, _ = Title.objects.update_or_create(
            original_name='Interstellar',
            defaults={
                'type': Title.Type.MOVIE,
                'name': 'Interstellar',
                'description': 'A team of explorers travel through a wormhole in space...',
                'release_year': 2014,
                'rating_score': 8.7,
                'votes_count': 150
            }
        )
        movie.genres.set(genres[:2])

        series, _ = Title.objects.update_or_create(
            original_name='The Boys',
            defaults={
                'type': Title.Type.SERIES,
                'name': 'The Boys',
                'description': 'A group of vigilantes set out to take down corrupt superheroes...',
                'release_year': 2019,
                'rating_score': 8.5,
                'votes_count': 90
            }
        )
        series.genres.set(genres[2:4])

        # 4. Create Episodes
        for i in range(1, 4):
            Episode.objects.update_or_create(
                title=series,
                season_number=1,
                episode_number=i,
                defaults={'name': f'Episode {i}'}
            )

        # 5. Create Transcoding Presets (Requested by user)
        presets_data = [
            # Video Presets
            {
                'name': '4K AV1 5M', 'type': 'VIDEO', 'codec': 'libaom-av1',
                'bitrate': '5M', 'width': 3840, 'container': 'm3u8',
                'video_preset': '', 'custom_post_args': '-strict experimental'
            },
            {
                'name': 'FHD libx264 4M', 'type': 'VIDEO', 'codec': 'libx264',
                'bitrate': '4M', 'width': 1920, 'container': 'm3u8', 'video_preset': 'medium'
            },
            {
                'name': 'HD libx264 2M', 'type': 'VIDEO', 'codec': 'libx264',
                'bitrate': '2M', 'width': 1280, 'container': 'm3u8', 'video_preset': 'fast'
            },
            {
                'name': 'SD libx264 1M', 'type': 'VIDEO', 'codec': 'libx264',
                'bitrate': '1M', 'width': 854, 'container': 'm3u8', 'video_preset': 'veryfast'
            },
            # Audio Presets
            {
                'name': 'HQ libopus 224k', 'type': 'AUDIO', 'codec': 'libopus',
                'bitrate': '224k', 'container': 'webm'
            },
            {
                'name': 'SQ aac 128k', 'type': 'AUDIO', 'codec': 'aac',
                'bitrate': '128k', 'container': 'm4a'
            },
        ]

        preset_objs = {}
        for p_info in presets_data:
            p, _ = TranscodingPreset.objects.update_or_create(name=p_info['name'], defaults=p_info)
            preset_objs[p.name] = p

        # 6. Create Logical Assets
        video_asset, _ = Asset.objects.get_or_create(
            id='7b9b7017-6349-4fdd-963e-dd33bd6fb819',
            defaults={'type': Asset.Type.VIDEO}
        )
        audio_asset, _ = Asset.objects.get_or_create(
            id='0a430e30-08e0-4ff8-85a2-d4c2be496efb',
            defaults={'type': Asset.Type.AUDIO}
        )

        # 7. Create Physical Variants (Mocking READY status for testing)
        # Video Variants
        AssetVariant.objects.update_or_create(
            asset=video_asset, preset=preset_objs['FHD libx264 4M'],
            defaults={
                'status': AssetVariant.Status.READY,
                'storage_path': 'assets/sample/master_1080.m3u8',
                'quality_label': '1080p'
            }
        )
        AssetVariant.objects.update_or_create(
            asset=video_asset, preset=preset_objs['HD libx264 2M'],
            defaults={
                'status': AssetVariant.Status.READY,
                'storage_path': 'assets/sample/master_720.m3u8',
                'quality_label': '720p'
            }
        )
        # Audio Variants
        AssetVariant.objects.update_or_create(
            asset=audio_asset, preset=preset_objs['SQ aac 128k'],
            defaults={
                'status': AssetVariant.Status.READY,
                'storage_path': 'assets/sample/audio_ru.m4a',
                'quality_label': 'Standard (AAC)'
            }
        )

        # 8. Create Virtual Composition (TrackGroup)
        movie_ctype = ContentType.objects.get_for_model(Title)
        tg_movie, _ = TrackGroup.objects.update_or_create(
            content_type=movie_ctype,
            object_id=movie.id,
            name='Theatrical Version',
            defaults={'video_asset': video_asset}
        )
        AdditionalTrack.objects.update_or_create(
            track_group=tg_movie,
            language='Russian (Dub)',
            defaults={'asset': audio_asset, 'offset_ms': 0}
        )

        # 9. Create Plugin Provider
        PluginProvider.objects.update_or_create(
            name='Mock Global Balancer',
            defaults={
                'endpoint_url': 'http://localhost:3101/resolve',
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded database with logical assets and variants!'))
