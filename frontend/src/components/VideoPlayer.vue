<script setup>
import {computed, nextTick, onBeforeUnmount, onMounted, ref, watch} from 'vue';
import Hls from 'hls.js';

const props = defineProps({
  contentId: {type: String, required: true},
  contentType: {type: String, default: 'title'},
  titleId: {type: String, required: true},
  episodeId: {type: String, default: ''},
  startProgress: {type: [String, Number], default: 0},
  lastTrackGroup: {type: [String, Number], default: ''},
  lastAudioAsset: {type: String, default: ''},
  lastQuality: {type: String, default: ''},
  csrfToken: {type: String, required: true}
});

const videoRef = ref(null);
const audioRef = ref(null);
const wrapperRef = ref(null);

const isLoading = ref(true);
const manifest = ref(null);
const error = ref(null);

const groupedSources = ref({});
const activeGroupId = ref(null);
const activeVideo = ref(null);
const activeAudio = ref(null);
const hasResumed = ref(false);

let hlsVideo = null;
let hlsAudio = null;
let syncInterval = null;
let telemetryInterval = null;

const fetchManifest = async () => {
  isLoading.value = true;
  try {
    const response = await fetch(`/api/v1/player/manifest/${props.contentType}/${props.contentId}/`);
    manifest.value = await response.json();
    processSources(manifest.value.sources);

    const groupKeys = Object.keys(groupedSources.value);
    if (groupKeys.length > 0) {
      const rememberedId = groupKeys.find(k => String(k) === String(props.lastTrackGroup));
      const targetGroup = rememberedId || groupKeys[0];

      await selectGroup(targetGroup);
    }

    fetchExternalSources();
  } catch (e) {
    console.error("Manifest error:", e);
    error.value = "Failed to load video manifest.";
  } finally {
    isLoading.value = false;
  }
};

const fetchExternalSources = async () => {
  try {
    const response = await fetch(`/api/v1/player/manifest/external/${props.contentType}/${props.contentId}/`);
    if (response.ok) {
      const extData = await response.json();
      if (extData.sources && extData.sources.length > 0) {
        processSources(extData.sources);
        if (!activeGroupId.value) {
          const groupKeys = Object.keys(groupedSources.value);
          if (groupKeys.length > 0) selectGroup(groupKeys[0]);
        }
      }
    }
  } catch (e) {
    console.warn("External sources warning:", e);
  }
};

const processSources = (sources) => {
  const groups = {};
  sources.forEach(source => {
    if (source.type === 'EXTERNAL_PLAYER') {
      groups[source.asset_id] = {
        title: source.provider || 'External Source',
        video: source,
        audios: []
      };
      return;
    }
    const gid = source.sync_group_id;
    if (!gid) return;
    if (!groups[gid]) {
      groups[gid] = {title: source.group_title || 'Default', video: null, audios: []};
    }
    if (source.type === 'VIDEO') {
      groups[gid].video = source;
    } else if (source.type === 'AUDIO') {
      groups[gid].audios.push(source);
    }
  });
  groupedSources.value = {...groupedSources.value, ...groups};
};

const initHls = (mediaElement, source, hlsInstanceVar, isVideo = false) => {
  if (!mediaElement) return null;

  if (hlsInstanceVar) {
    hlsInstanceVar.destroy();
  }

  const targetPath = source.active_path || source.storage_path;
  const startSec = (isVideo && !hasResumed.value && props.startProgress) ? parseInt(props.startProgress) / 1000 : -1;

  if (Hls.isSupported() && targetPath.endsWith('.m3u8')) {
    const config = {enableWorker: true};
    if (startSec > 0) {
      config.startPosition = startSec;
      hasResumed.value = true;
    }

    const hls = new Hls(config);
    hls.loadSource(targetPath);
    hls.attachMedia(mediaElement);
    hls.on(Hls.Events.ERROR, function (event, data) {
      if (data.fatal) {
        console.error("HLS Fatal Error:", data);
        error.value = "Playback error occurred.";
      }
    });
    return hls;
  } else if (mediaElement.canPlayType && mediaElement.canPlayType('application/vnd.apple.mpegurl')) {
    mediaElement.src = targetPath;
    if (startSec > 0) {
      mediaElement.addEventListener('loadedmetadata', () => {
        mediaElement.currentTime = startSec;
        hasResumed.value = true;
      }, {once: true});
    }
    return null;
  } else {
    mediaElement.src = targetPath;
    if (startSec > 0) {
      mediaElement.addEventListener('loadedmetadata', () => {
        mediaElement.currentTime = startSec;
        hasResumed.value = true;
      }, {once: true});
    }
    return null;
  }
};

const selectGroup = async (groupId) => {
  activeGroupId.value = groupId;
  const group = groupedSources.value[groupId];

  if (!group) return;

  activeVideo.value = null;
  activeAudio.value = null;

  await nextTick();

  activeVideo.value = group.video;

  // Восстановление Аудио-дорожки
  if (group.audios.length > 0) {
    if (props.lastAudioAsset) {
      const rememberedAudio = group.audios.find(a => a.asset_id === props.lastAudioAsset);
      activeAudio.value = rememberedAudio || group.audios[0];
    } else {
      activeAudio.value = group.audios[0];
    }
  } else {
    activeAudio.value = null;
  }

  // Восстановление Видео-качества
  if (activeVideo.value && activeVideo.value.qualities?.length > 0) {
    let matchedQuality = null;
    if (props.lastQuality) {
      matchedQuality = activeVideo.value.qualities.find(q => q.label === props.lastQuality);
    }

    // Перезаписываем дефолтный путь от бэкенда, если нашли сохраненное качество
    if (matchedQuality) {
      activeVideo.value.active_path = matchedQuality.storage_path;
    } else if (!activeVideo.value.active_path) {
      activeVideo.value.active_path = activeVideo.value.qualities[0].storage_path;
    }
  }

  // Гарантируем active_path для аудио
  if (activeAudio.value && !activeAudio.value.active_path && activeAudio.value.qualities?.length > 0) {
    activeAudio.value.active_path = activeAudio.value.qualities[0].storage_path;
  }

  if (activeVideo.value?.type === 'VIDEO') {
    startSyncEngine();
  } else {
    stopSyncEngine();
  }
};

watch(videoRef, (newEl) => {
  if (newEl && activeVideo.value && activeVideo.value.type === 'VIDEO') {
    hlsVideo = initHls(newEl, activeVideo.value, hlsVideo, true);
    newEl.load();
  }
});

watch(audioRef, (newEl) => {
  if (newEl && activeAudio.value) {
    hlsAudio = initHls(newEl, activeAudio.value, hlsAudio, false);
    newEl.load();
  }
});

const selectAudio = async (audioSource) => {
  const currentTime = videoRef.value.currentTime;
  const isPlaying = !videoRef.value.paused;

  if (audioSource) {
    if (!audioSource.active_path && audioSource.qualities?.length > 0) {
      audioSource.active_path = audioSource.qualities[0].storage_path;
    }
    activeAudio.value = audioSource;
  } else {
    activeAudio.value = null;
  }

  await nextTick();

  if (activeAudio.value) {
    hlsAudio = initHls(audioRef.value, activeAudio.value, hlsAudio, false);
  } else if (hlsAudio) {
    hlsAudio.destroy();
    hlsAudio = null;
  }

  videoRef.value.currentTime = currentTime;
  if (isPlaying) videoRef.value.play();
};

const changeVideoQuality = async (path) => {
  if (!activeVideo.value || activeVideo.value.active_path === path) return;

  const currentTime = videoRef.value.currentTime;
  const isPaused = videoRef.value.paused;
  activeVideo.value.active_path = path;

  hlsVideo = initHls(videoRef.value, activeVideo.value, hlsVideo, true);

  videoRef.value.currentTime = currentTime;
  if (!isPaused) videoRef.value.play().catch(e => console.warn(e));
};

const changeAudioQuality = async (path) => {
  if (!audioRef.value || activeAudio.value.active_path === path) return;

  const currentTime = videoRef.value.currentTime;
  const isPaused = videoRef.value.paused;

  activeAudio.value.active_path = path;
  hlsAudio = initHls(audioRef.value, activeAudio.value, hlsAudio, false);

  const offsetSeconds = (activeAudio.value.offset_ms || 0) / 1000;
  audioRef.value.currentTime = currentTime - offsetSeconds;

  if (!isPaused) audioRef.value.play().catch(e => console.warn("Audio resume failed", e));
};

const performSync = () => {
  if (!videoRef.value || !audioRef.value || !activeAudio.value) return;

  const video = videoRef.value;
  const audio = audioRef.value;

  if (video.paused || video.waiting || video.seeking) {
    if (!audio.paused) audio.pause();
    return;
  }

  const offsetSeconds = activeAudio.value.offset_ms / 1000;
  const targetAudioTime = video.currentTime - offsetSeconds;

  const diff = Math.abs(audio.currentTime - targetAudioTime);
  if (diff > 0.2) {
    audio.currentTime = targetAudioTime;
  }

  if (audio.paused) {
    audio.play().catch(e => console.warn("Audio play blocked", e));
  }
};

const startSyncEngine = () => {
  stopSyncEngine();
  syncInterval = setInterval(performSync, 250);
};

const stopSyncEngine = () => {
  if (syncInterval) clearInterval(syncInterval);
};

const handleVideoEvents = () => {
  performSync();
};

const sendTelemetry = async () => {
  if (!videoRef.value) return;

  const currentMs = Math.floor(videoRef.value.currentTime * 1000);
  const duration = videoRef.value.duration || 0;
  const isCompleted = duration > 0 && (videoRef.value.currentTime / duration) > 0.95;
  const tGroupId = parseInt(activeGroupId.value);

  // Собираем текущие данные о качестве и аудио
  let currentQualityLabel = null;
  if (activeVideo.value && activeVideo.value.qualities) {
    const q = activeVideo.value.qualities.find(q => q.storage_path === activeVideo.value.active_path);
    if (q) currentQualityLabel = q.label;
  }
  const currentAudioAssetId = activeAudio.value ? activeAudio.value.asset_id : null;

  try {
    await fetch('/api/v1/player/telemetry/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({
        title_id: props.titleId,
        episode_id: props.episodeId || null,
        track_group_id: isNaN(tGroupId) ? null : tGroupId,
        audio_asset_id: currentAudioAssetId,
        quality_label: currentQualityLabel,
        progress_ms: currentMs,
        is_completed: isCompleted
      })
    });
  } catch (e) {
    console.warn("Telemetry ping failed", e);
  }
};

const startTelemetry = () => {
  if (telemetryInterval) clearInterval(telemetryInterval);
  telemetryInterval = setInterval(() => {
    if (videoRef.value && !videoRef.value.paused) {
      sendTelemetry();
    }
  }, 10000);
};

const stopTelemetry = () => {
  if (telemetryInterval) clearInterval(telemetryInterval);
};

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    wrapperRef.value.requestFullscreen().catch(err => console.error(err));
  } else {
    document.exitFullscreen();
  }
};

onMounted(() => {
  fetchManifest();
  startTelemetry();
});

onBeforeUnmount(() => {
  stopSyncEngine();
  stopTelemetry();
  sendTelemetry();
  if (hlsVideo) hlsVideo.destroy();
  if (hlsAudio) hlsAudio.destroy();
});

const currentGroupAudios = computed(() => {
  return activeGroupId.value && groupedSources.value[activeGroupId.value]
      ? groupedSources.value[activeGroupId.value].audios
      : [];
});
</script>

<template>
  <div class="video-player-container" ref="wrapperRef">
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center bg-black z-20">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

    <div v-else-if="error"
         class="absolute inset-0 flex flex-col items-center justify-center bg-black text-gray-400 z-20">
      <svg class="w-12 h-12 mb-4 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
      </svg>
      <span class="text-lg font-bold">{{ error }}</span>
    </div>

    <div v-else class="relative w-full h-full bg-black group">

      <video
          v-if="activeVideo && activeVideo.type === 'VIDEO'"
          ref="videoRef"
          class="w-full h-full"
          controls
          playsinline
          crossorigin="anonymous"
          :muted="!!activeAudio"
          @play="handleVideoEvents"
          @pause="handleVideoEvents"
          @seeked="handleVideoEvents"
          @waiting="handleVideoEvents"
      ></video>

      <iframe
          v-else-if="activeVideo && activeVideo.type === 'EXTERNAL_PLAYER'"
          :src="activeVideo.storage_path"
          class="w-full h-full border-0"
          allowfullscreen
          allow="autoplay; encrypted-media"
      ></iframe>

      <audio v-if="activeAudio" ref="audioRef" class="hidden" preload="auto"></audio>

      <!-- TOP OVERLAY -->
      <div
          class="absolute top-0 left-0 right-0 p-4 bg-gradient-to-b from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex justify-between items-start pointer-events-none">

        <div class="pointer-events-auto flex flex-col gap-2">
          <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Version</label>
          <div class="flex flex-wrap gap-2">
            <button
                v-for="(group, id) in groupedSources" :key="id" @click="selectGroup(id)"
                :class="['px-3 py-1 text-sm rounded transition-colors border', activeGroupId === id ? 'bg-brand border-brand text-white' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']"
            >
              {{ group.title }}
            </button>
          </div>
        </div>

        <div class="flex gap-2">
          <button @click="toggleFullscreen"
                  class="pointer-events-auto text-white hover:text-brand bg-black/50 p-2 rounded">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- BOTTOM OVERLAY -->
      <div
          class="absolute bottom-16 left-0 right-0 px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none flex flex-col gap-4">

        <!-- 1. Ряд выбора дорожки и её качества -->
        <div v-if="currentGroupAudios.length > 0" class="flex justify-between items-end">
          <div class="pointer-events-auto flex flex-col gap-2">
            <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Audio Track</label>
            <div class="flex flex-wrap gap-2">
              <button @click="selectAudio(null)"
                      :class="['px-3 py-1 text-sm rounded transition-colors border', activeAudio === null ? 'bg-white text-black border-white' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']">
                Original
              </button>
              <button v-for="audio in currentGroupAudios" :key="audio.id" @click="selectAudio(audio)"
                      :class="['px-3 py-1 text-sm rounded transition-colors border', activeAudio?.id === audio.id ? 'bg-white text-black border-white' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']">
                {{ audio.meta_info?.language || 'Dub' }}
              </button>
            </div>
          </div>

          <div v-if="activeAudio && activeAudio.qualities?.length > 1"
               class="pointer-events-auto flex flex-col gap-2 items-end ml-auto">
            <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Audio Quality</label>
            <div class="flex flex-wrap gap-2 justify-end">
              <button v-for="q in activeAudio.qualities" :key="q.variant_id" @click="changeAudioQuality(q.storage_path)"
                      :class="['px-3 py-1 text-sm rounded transition-colors border', activeAudio.active_path === q.storage_path ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']">
                {{ q.label }}
              </button>
            </div>
          </div>
        </div>

        <!-- 2. Ряд выбора видео-качества -->
        <div v-if="activeVideo && activeVideo.qualities && activeVideo.qualities.length > 1" class="flex justify-end">
          <div class="pointer-events-auto flex flex-col gap-2 items-end">
            <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Video Quality</label>
            <div class="flex flex-wrap gap-2 justify-end">
              <button v-for="q in activeVideo.qualities" :key="q.variant_id" @click="changeVideoQuality(q.storage_path)"
                      :class="['px-3 py-1 text-sm rounded transition-colors border', activeVideo.active_path === q.storage_path ? 'bg-brand text-white border-brand' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']">
                {{ q.label }}
              </button>
            </div>
          </div>
        </div>

      </div>

    </div>
  </div>
</template>

<style scoped>
.video-player-container {
  position: relative;
  width: 100%;
  height: 100%;
  aspect-ratio: 16 / 9;
  background-color: black;
  border-radius: 0.5rem;
  overflow: hidden;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}
</style>