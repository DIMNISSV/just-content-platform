(function () {
    console.log("JCP Plugin Script: Kodik Telemetry Integrated");

    // Состояние плеера, которое мы собираем из postMessage
    const playerState = {
        currentTime: 0,
        duration: 0,
        translationName: 'Unknown',
        isEnded: false
    };

    const bridge = window.JCP_PlayerBridge;
    if (!bridge) {
        console.error("JCP_PlayerBridge not found. Telemetry cannot be started.");
        return;
    }

    /**
     * Обработчик сообщений от iframe плеера Kodik
     */
    const kodikMessageListener = (event) => {
        // Проверяем, что сообщение пришло от Kodik (опционально можно добавить проверку event.origin)
        if (!event.data || typeof event.data !== 'object') return;

        const {key, value} = event.data;

        switch (key) {
            case 'kodik_player_time_update':
                playerState.currentTime = value;
                break;

            case 'kodik_player_duration_update':
                playerState.duration = value;
                break;

            case 'kodik_player_current_episode':
                if (value && value.translation) {
                    playerState.translationName = value.translation.title;
                }
                break;

            case 'kodik_player_video_ended':
                playerState.isEnded = true;
                break;

            case 'kodik_player_seek':
                // При перемотке можно отправить телеметрию немедленно
                sendTelemetryToBridge();
                break;
        }
    };

    // Подписка на сообщения от iframe
    window.addEventListener('message', kodikMessageListener);

    /**
     * Формирует пакет данных и отправляет его в Vue-приложение
     */
    const sendTelemetryToBridge = () => {
        // Вычисляем завершенность (если просмотрено более 95%)
        const isCompleted = playerState.duration > 0 &&
            (playerState.currentTime / playerState.duration > 0.95) ||
            playerState.isEnded;

        const payload = {
            progress_ms: Math.floor(playerState.currentTime * 1000),
            is_completed: isCompleted,
            track_group_id: null, // Определяется на стороне сайта через сессию
            audio_asset_id: null,
            audio_track_name: playerState.translationName,
            quality_label: 'Auto' // Kodik API не присылает текущее качество в time_update
        };

        console.log("Plugin -> Bridge: Sending Real Telemetry", payload);
        bridge.sendTelemetry(payload);
    };

    // Отправляем данные каждые 15 секунд, чтобы не перегружать сервер
    setInterval(sendTelemetryToBridge, 15000);

    // Первичная отправка через пару секунд после загрузки
    setTimeout(sendTelemetryToBridge, 2000);
})();