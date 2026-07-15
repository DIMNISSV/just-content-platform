import {ref} from 'vue';
import Hls from 'hls.js';

export function useSyncPlayer() {
    const videoRef = ref(null);
    const audioRef = ref(null);
    const isPlaying = ref(false);
    const currentTime = ref(0);
    const duration = ref(0);
    const volume = ref(1);
    const isMuted = ref(false);
    const playbackRate = ref(1);

    let hlsVideo = null;
    let hlsAudio = null;
    let syncInterval = null;

    const performSync = (activeAudio) => {
        if (!videoRef.value || !audioRef.value || !activeAudio) return;
        const video = videoRef.value;
        const audio = audioRef.value;

        if (video.paused || video.waiting || video.seeking) {
            if (!audio.paused) audio.pause();
            return;
        }
        if (audio.readyState < 2) {
            if (!video.paused) video.pause();
            return;
        } else {
            if (video.paused && isPlaying.value) {
                video.play().catch(() => {
                });
            }
        }

        const offsetSeconds = activeAudio.offset_ms / 1000;
        const targetAudioTime = video.currentTime - offsetSeconds;
        const drift = Math.abs(audio.currentTime - targetAudioTime);
        if (drift > 0.25) {
            audio.currentTime = targetAudioTime;
        }
        if (audio.paused && !video.paused) {
            audio.play().catch(e => console.warn("Audio blocked by browser:", e));
        }
    };

    const startSyncEngine = (activeAudio) => {
        stopSyncEngine();
        syncInterval = setInterval(() => performSync(activeAudio), 250);
    };

    const stopSyncEngine = () => {
        if (syncInterval) {
            clearInterval(syncInterval);
            syncInterval = null;
        }
    };

    const initHls = (mediaElement, source, isVideo, startProgress, hasResumed) => {
        if (!mediaElement) return null;

        if (isVideo && hlsVideo) {
            hlsVideo.destroy();
            hlsVideo = null;
        } else if (!isVideo && hlsAudio) {
            hlsAudio.destroy();
            hlsAudio = null;
        }

        if (!source) return null;

        const targetPath = source.active_path || source.storage_path;
        const startSec = (isVideo && !hasResumed && startProgress) ? parseInt(startProgress) / 1000 : -1;

        if (Hls.isSupported() && targetPath.endsWith('.m3u8')) {
            const config = {enableWorker: true};
            if (startSec > 0) {
                config.startPosition = startSec;
            }
            const hls = new Hls(config);
            hls.loadSource(targetPath);
            hls.attachMedia(mediaElement);
            hls.on(Hls.Events.ERROR, (event, data) => {
                if (data.fatal) console.error("HLS Fatal Error:", data);
            });

            if (isVideo) hlsVideo = hls;
            else hlsAudio = hls;

            return hls;
        } else {
            mediaElement.src = targetPath;
            if (startSec > 0) {
                mediaElement.addEventListener('loadedmetadata', () => {
                    mediaElement.currentTime = startSec;
                }, {once: true});
            }
            return null;
        }
    };

    const destroyHls = () => {
        if (hlsVideo) {
            hlsVideo.destroy();
            hlsVideo = null;
        }
        if (hlsAudio) {
            hlsAudio.destroy();
            hlsAudio = null;
        }
    };

    const togglePlay = () => {
        if (!videoRef.value) return;
        if (videoRef.value.paused) {
            videoRef.value.play().catch(e => console.warn(e));
        } else {
            videoRef.value.pause();
        }
    };

    const skip = (seconds) => {
        if (videoRef.value) {
            videoRef.value.currentTime += seconds;
        }
    };

    const seek = (timeInSeconds) => {
        if (videoRef.value) {
            videoRef.value.currentTime = timeInSeconds;
        }
    };

    const setVolume = (val) => {
        volume.value = val;
        if (videoRef.value) videoRef.value.volume = val;
        if (audioRef.value) audioRef.value.volume = val;
        isMuted.value = val === 0;
    };

    const toggleMute = () => {
        isMuted.value = !isMuted.value;
        if (videoRef.value) videoRef.value.muted = isMuted.value;
        if (audioRef.value) audioRef.value.muted = isMuted.value;
    };

    const changePlaybackRate = (rate) => {
        const newRate = parseFloat(rate);
        if (isNaN(newRate)) return;
        playbackRate.value = newRate;
        if (videoRef.value) videoRef.value.playbackRate = newRate;
        if (audioRef.value) audioRef.value.playbackRate = newRate;
    };

    return {
        videoRef,
        audioRef,
        isPlaying,
        currentTime,
        duration,
        volume,
        isMuted,
        playbackRate,
        initHls,
        destroyHls,
        performSync,
        startSyncEngine,
        stopSyncEngine,
        togglePlay,
        skip,
        seek,
        setVolume,
        toggleMute,
        changePlaybackRate
    };
}