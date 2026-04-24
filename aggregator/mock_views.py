from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def mock_manifest_view(request):
    """
    Имитирует ответ внешнего плагина с данными манифеста (deep integration).
    Отдает фиктивную аудиодорожку, которая будет 'подклеиваться' к локальному видео.
    """
    # В реальном плагине мы бы искали контент по request.data.get('external_ids')
    return Response({
        "sources": [
            {
                "id": "mock_audio_1",
                "asset_id": "mock_asset_uuid_001",
                "type": "AUDIO",
                "sync_group_id": None,  # Укажем позже при динамическом матчинге
                "group_title": "Mock Plugin Version",
                "offset_ms": 0,
                "meta_info": {"language": "JPN (Mock Dub)"},
                "qualities": [
                    {
                        "variant_id": "mock_var_1",
                        "label": "Standard Mock Audio",
                        # Используем тестовый HLS-стрим для проверки (видео-тестовый стрим, но для аудио сойдет как заглушка)
                        "storage_path": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
                    }
                ],
                "active_path": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
            }
        ]
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def mock_iframe_view(request):
    """
    Имитирует внешний глобальный плеер (Entity iFrame / Episode iFrame).
    """
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mock External Player</title>
        <style>
            body { 
                background: #111; 
                color: #fff; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                height: 100vh; 
                margin: 0; 
                font-family: sans-serif;
                overflow: hidden;
            }
            .player-box {
                border: 2px dashed #e50914;
                padding: 40px;
                border-radius: 10px;
                text-align: center;
                background: rgba(229, 9, 20, 0.1);
            }
            h1 { margin: 0 0 10px 0; font-size: 24px; }
            p { color: #888; font-size: 14px; margin: 0; }
        </style>
    </head>
    <body>
        <div class="player-box">
            <h1>EXTERNAL PLAYER MOCK</h1>
            <p>This is an iframe served by a 3rd party plugin.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)
