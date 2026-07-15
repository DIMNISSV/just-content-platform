import {ref} from 'vue';

export function usePlayerTelemetry(props, activeGroupId, activeVideo, activeAudio, videoRef, getAudioFullName) {
    const isLoading = ref(true);
    const manifest = ref(null);
    const error = ref(null);
    const nextEpisodeId = ref(null);

    let telemetryInterval = null;
    let heartbeatInterval = null;

    const fetchManifest = async () => {
        isLoading.value = true;
        try {
            const response = await fetch(`/api/v1/player/manifest/${props.contentType}/${props.contentId}/`);
            if (!response.ok) throw new Error("Manifest load failed");
            manifest.value = await response.json();
            nextEpisodeId.value = manifest.value.next_episode_id || null;
            return manifest.value.sources;
        } catch (e) {
            error.value = "Не удалось загрузить манифест воспроизведения.";
            return [];
        } finally {
            isLoading.value = false;
        }
    };

    const sendTelemetry = async () => {
        if (!videoRef.value || isNaN(videoRef.value.duration)) return;
        const currentMs = Math.floor(videoRef.value.currentTime * 1000);
        const dur = videoRef.value.duration || 0;
        const isCompleted = dur > 0 && (videoRef.value.currentTime / dur) > 0.95;
        const tGroupId = parseInt(activeGroupId.value);

        const currentQualityLabel = activeVideo.value?.qualities?.find(
            q => q.storage_path === activeVideo.value.active_path
        )?.label || null;
        const currentAudioAssetId = activeAudio.value ? activeAudio.value.asset_id : null;
        const currentAudioTrackName = getAudioFullName(activeAudio.value);

        const endpoint = props.episodeId
            ? '/api/v1/player/episode-telemetry/'
            : '/api/v1/player/telemetry/';

        const payload = {
            progress_ms: currentMs,
            is_completed: isCompleted,
            track_group_id: isNaN(tGroupId) ? null : tGroupId,
            audio_asset_id: currentAudioAssetId,
            audio_track_name: currentAudioTrackName,
            quality_label: currentQualityLabel,
        };

        if (!props.episodeId) {
            payload.title_id = props.titleId;
        } else {
            payload.episode_id = props.episodeId;
        }

        try {
            await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': props.csrfToken
                },
                body: JSON.stringify(payload)
            });
        } catch (e) {
            // Игнорируем сетевые сбои телеметрии
        }
    };

    const sendHeartbeat = async () => {
        if (!props.sessionToken) return;

        try {
            const response = await fetch('/api/v1/player/session/heartbeat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': props.csrfToken
                },
                body: JSON.stringify({
                    session_token: props.sessionToken
                })
            });

            if (!response.ok) {
                console.warn("Viewing session heartbeat failed. Session may have expired.");
            }
        } catch (e) {
            console.error("Network error during heartbeat:", e);
        }
    };

    const startTelemetry = () => {
        stopTelemetry();

        // Telemetry interval (every 10 seconds if playing)
        telemetryInterval = setInterval(() => {
            if (videoRef.value && !videoRef.value.paused) {
                sendTelemetry();
            }
        }, 10000);

        // Heartbeat interval (every 10 minutes to keep session alive)
        if (props.sessionToken) {
            sendHeartbeat(); // Initial heartbeat
            heartbeatInterval = setInterval(sendHeartbeat, 10 * 60 * 1000);
        }
    };

    const stopTelemetry = () => {
        if (telemetryInterval) {
            clearInterval(telemetryInterval);
            telemetryInterval = null;
        }
        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
            heartbeatInterval = null;
        }
    };

    return {
        isLoading,
        manifest,
        error,
        nextEpisodeId,
        fetchManifest,
        sendTelemetry,
        startTelemetry,
        stopTelemetry
    };
}