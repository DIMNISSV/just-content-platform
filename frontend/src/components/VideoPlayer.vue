<script setup>
import {computed, nextTick, onBeforeUnmount, onMounted, ref} from 'vue';
import Hls from 'hls.js';

const props = defineProps({
  contentId: {type: String, required: true},
  contentType: {type: String, default: 'title'}
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

let hlsVideo = null;
let hlsAudio = null;
let syncInterval = null;

const fetchManifest = async () => {
  isLoading.value = true;
  try {
    const response = await fetch(`/api/v1/player/manifest/${props.contentType}/${props.contentId}/`);
    manifest.value = await response.json();
    processSources(manifest.value.sources);

    const groupKeys = Object.keys(groupedSources.value);
    if (groupKeys.length > 0) {
      selectGroup(groupKeys[0]);
    }

    fetchExternalSources();
  } catch (e) {
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
  groupedSources.value = groups;
};

const initHls = (mediaElement, source, hlsInstanceVar) => {
  if (hlsInstanceVar) {
    hlsInstanceVar.destroy();
  }

  // Берем active_path, если он передан (для переключения качества), иначе fallback
  const targetPath = source.active_path || source.storage_path;

  if (Hls.isSupported() && targetPath.endsWith('.m3u8')) {
    const hls = new Hls({enableWorker: true});
    hls.loadSource(targetPath);
    hls.attachMedia(mediaElement);
    hls.on(Hls.Events.ERROR, function (event, data) {
      if (data.fatal) {
        console.error("HLS Fatal Error:", data);
        error.value = "Playback error occurred.";
      }
    });
    return hls;
  } else if (mediaElement.canPlayType('application/vnd.apple.mpegurl')) {
    mediaElement.src = targetPath;
    return null;
  } else {
    mediaElement.src = targetPath;
    return null;
  }
};

const selectGroup = async (groupId) => {
  activeGroupId.value = groupId;
  const group = groupedSources.value[groupId];

  activeVideo.value = group.video;
  activeAudio.value = group.audios.length > 0 ? group.audios[0] : null;

  await nextTick();

  if (activeVideo.value && activeVideo.value.type === 'VIDEO') {
    hlsVideo = initHls(videoRef.value, activeVideo.value, hlsVideo);
    if (activeAudio.value) {
      hlsAudio = initHls(audioRef.value, activeAudio.value, hlsAudio);
    }
    startSyncEngine();
  } else {
    stopSyncEngine();
  }
};

const selectAudio = async (audioSource) => {
  const isPlaying = !videoRef.value.paused;
  const currentTime = videoRef.value.currentTime;

  activeAudio.value = audioSource;
  await nextTick();

  if (audioSource) {
    hlsAudio = initHls(audioRef.value, audioSource, hlsAudio);
  } else if (hlsAudio) {
    hlsAudio.destroy();
    hlsAudio = null;
  }

  videoRef.value.currentTime = currentTime;
  if (isPlaying) videoRef.value.play();
};

const changeVideoQuality = async (path) => {
  if (activeVideo.value.active_path === path) return;

  const currentTime = videoRef.value.currentTime;
  const isPaused = videoRef.value.paused;
  activeVideo.value.active_path = path;

  hlsVideo = initHls(videoRef.value, activeVideo.value, hlsVideo);

  videoRef.value.currentTime = currentTime;
  if (!isPaused) {
    videoRef.value.play().catch(e => console.warn(e));
  }
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

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    wrapperRef.value.requestFullscreen().catch(err => console.error(err));
  } else {
    document.exitFullscreen();
  }
};

onMounted(() => {
  fetchManifest();
});

onBeforeUnmount(() => {
  stopSyncEngine();
  if (hlsVideo) hlsVideo.destroy();
  if (hlsAudio) hlsAudio.destroy();
});

const currentGroupAudios = computed(() => {
  return activeGroupId.value ? groupedSources.value[activeGroupId.value].audios : [];
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
          class="absolute bottom-16 left-0 right-0 px-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none flex justify-between items-end">

        <!-- Audio selector -->
        <div v-if="currentGroupAudios.length > 0" class="pointer-events-auto flex flex-col gap-2">
          <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Audio Track</label>
          <div class="flex flex-wrap gap-2">
            <button
                @click="selectAudio(null)"
                :class="['px-3 py-1 text-sm rounded transition-colors border', activeAudio === null ? 'bg-white text-black border-white' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']"
            >
              Original (Native)
            </button>
            <button
                v-for="audio in currentGroupAudios" :key="audio.asset_id" @click="selectAudio(audio)"
                :class="['px-3 py-1 text-sm rounded transition-colors border', activeAudio?.asset_id === audio.asset_id ? 'bg-white text-black border-white' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']"
            >
              {{ audio.meta_info?.language || 'Dub Track' }}
            </button>
          </div>
        </div>

        <!-- Video Quality Selector -->
        <div v-if="activeVideo && activeVideo.qualities && activeVideo.qualities.length > 1"
             class="pointer-events-auto flex flex-col gap-2 items-end ml-auto">
          <label class="text-xs text-gray-400 font-bold uppercase tracking-wider">Quality</label>
          <div class="flex flex-wrap gap-2 justify-end">
            <button
                v-for="q in activeVideo.qualities" :key="q.asset_id" @click="changeVideoQuality(q.storage_path)"
                :class="['px-3 py-1 text-sm rounded transition-colors border', activeVideo.active_path === q.storage_path ? 'bg-brand text-white border-brand' : 'bg-gray-800/80 border-gray-600 text-gray-300 hover:bg-gray-700']"
            >
              {{ q.label }}
            </button>
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