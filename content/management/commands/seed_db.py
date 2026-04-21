from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from aggregator.models import PluginProvider
from content.models import Genre, Title, Episode, TrackGroup, AdditionalTrack
from media.models import RawMediaFile, Asset, TranscodingPreset

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds the database with initial test data without duplicates'

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

        # 3. Create a Movie
        movie, _ = Title.objects.update_or_create(
            original_name='Interstellar',
            defaults={
                'type': Title.Type.MOVIE,
                'name': 'Interstellar',
                'description': 'A team of explorers travel through a wormhole in space in an attempt to ensure humanity\'s survival.',
                'release_year': 2014,
                'rating_score': 8.7,
                'votes_count': 150
            }
        )
        movie.genres.set(genres[:2])  # Sci-Fi, Drama

        # 4. Create a Series
        series, _ = Title.objects.update_or_create(
            original_name='The Boys',
            defaults={
                'type': Title.Type.SERIES,
                'name': 'The Boys',
                'description': 'A group of vigilantes set out to take down corrupt superheroes who abuse their superpowers.',
                'release_year': 2019,
                'rating_score': 8.5,
                'votes_count': 90
            }
        )
        series.genres.set(genres[2:4])  # Action, Comedy

        # Create Episodes for S01
        for i in range(1, 4):
            Episode.objects.update_or_create(
                title=series,
                season_number=1,
                episode_number=i,
                defaults={
                    'name': f'Episode {i}',
                    'description': f'Description for episode {i}'
                }
            )

        # 5. Create Mock Media Assets
        video_asset, _ = Asset.objects.update_or_create(
            storage_path='assets/sample/master.m3u8',
            defaults={
                'type': Asset.Type.VIDEO,
                'status': Asset.Status.READY,
            }
        )
        audio_asset, _ = Asset.objects.update_or_create(
            storage_path='assets/sample/audio_ru.m4a',
            defaults={
                'type': Asset.Type.AUDIO,
                'status': Asset.Status.READY,
            }
        )

        # 6. Create Virtual Composition (TrackGroup)
        movie_ctype = ContentType.objects.get_for_model(Title)
        tg_movie, _ = TrackGroup.objects.update_or_create(
            content_type=movie_ctype,
            object_id=movie.id,
            name='Standard Version',
            defaults={
                'video_asset': video_asset
            }
        )
        AdditionalTrack.objects.update_or_create(
            track_group=tg_movie,
            language='RUS (Dub)',
            defaults={
                'asset': audio_asset,
                'offset_ms': 0
            }
        )

        # 7. Create Plugin Provider
        PluginProvider.objects.update_or_create(
            name='Mock Global Balancer',
            defaults={
                'endpoint_url': 'http://localhost:3101/resolve',
                'is_active': True
            }
        )

        presets_data = [
            # Video
            {'name': '4K AV1 5M', 'type': 'VIDEO', 'codec': 'libsvtav1', 'bitrate': '5M', 'width': 3840,
             'container': 'm3u8', 'video_preset': '6'},
            {'name': 'FHD x264 4M', 'type': 'VIDEO', 'codec': 'libx264', 'bitrate': '4M', 'width': 1920,
             'container': 'm3u8', 'video_preset': 'medium'},
            {'name': 'HD x264 2M', 'type': 'VIDEO', 'codec': 'libx264', 'bitrate': '2M', 'width': 1280,
             'container': 'm3u8', 'video_preset': 'fast'},
            {'name': 'SD x264 1M', 'type': 'VIDEO', 'codec': 'libx264', 'bitrate': '1M', 'width': 854,
             'container': 'm3u8', 'video_preset': 'veryfast'},
            # Audio
            {'name': 'HQ libopus 224k', 'type': 'AUDIO', 'codec': 'libopus', 'bitrate': '224k', 'container': 'opus'},
            {'name': 'SQ aac 128k', 'type': 'AUDIO', 'codec': 'aac', 'bitrate': '128k', 'container': 'm4a'},
        ]
        preset_objs = {}
        for p_info in presets_data:
            p, _ = TranscodingPreset.objects.update_or_create(name=p_info['name'], defaults=p_info)
            preset_objs[p.name] = p

        # Обновляем тестовые ассеты, чтобы увидеть качество в плеере
        video_asset.preset = preset_objs['FHD x264 4M']
        video_asset.quality_label = 'FHD x264 4M'
        video_asset.save()

        audio_asset.preset = preset_objs['SQ aac 128k']
        audio_asset.quality_label = 'SQ aac 128k'
        audio_asset.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded database with test data!'))
