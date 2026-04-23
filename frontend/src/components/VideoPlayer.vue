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
const progressRef = ref(null);

const isLoading = ref(true);
const manifest = ref(null);
const error = ref(null);

const groupedSources = ref({});
const activeGroupId = ref(null);
const activeVideo = ref(null);
const activeAudio = ref(null);
const hasResumed = ref(false);
const nextEpisodeId = ref(null);

// State для UI контролов
const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const volume = ref(1);
const isMuted = ref(false);
const showControls = ref(true);
const isFullscreen = ref(false);
const showSettingsMenu = ref(false);
const playbackRate = ref(1);

// State для рейтинга озвучки
const showTrackRating = ref(false);
const hoverTrackScore = ref(0);
const trackRatingMessage = ref('');
const trackRatingSubmitting = ref(false);

let hlsVideo = null;
let hlsAudio = null;
let syncInterval = null;
let telemetryInterval = null;
let controlsTimeout = null;

const formatTime = (timeInSeconds) => {
  if (isNaN(timeInSeconds)) return '00:00';
  const m = Math.floor(timeInSeconds / 60);
  const s = Math.floor(timeInSeconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const resetControlsTimer = () => {
  showControls.value = true;
  clearTimeout(controlsTimeout);
  controlsTimeout = setTimeout(() => {
    if (isPlaying.value) {
      showControls.value = false;
      showSettingsMenu.value = false;
      showTrackRating.value = false;
    }
  }, 3000);
};

const handleMouseLeave = () => {
  if (isPlaying.value) showControls.value = false;
};

const fetchManifest = async () => {
  isLoading.value = true;
  try {
    const response = await fetch(`/api/v1/player/manifest/${props.contentType}/${props.contentId}/`);
    manifest.value = await response.json();
    nextEpisodeId.value = manifest.value.next_episode_id || null;
    processSources(manifest.value.sources);

    const groupKeys = Object.keys(groupedSources.value);
    if (groupKeys.length > 0) {
      const rememberedId = groupKeys.find(k => String(k) === String(props.lastTrackGroup));
      const targetGroup = rememberedId || groupKeys[0];
      await selectGroup(targetGroup);
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
  }
};

const processSources = (sources) => {
  const groups = {};
  sources.forEach(source => {
    if (source.type === 'EXTERNAL_PLAYER') {
      groups[source.asset_id] = {title: source.provider || 'External Source', video: source, audios: []};
      return;
    }
    const gid = source.sync_group_id;
    if (!gid) return;
    if (!groups[gid]) groups[gid] = {title: source.group_title || 'Default', video: null, audios: []};

    if (source.type === 'VIDEO') groups[gid].video = source;
    else if (source.type === 'AUDIO') groups[gid].audios.push(source);
  });
  groupedSources.value = {...groupedSources.value, ...groups};
};

const initHls = (mediaElement, source, hlsInstanceVar, isVideo = false) => {
  if (!mediaElement) return null;
  if (hlsInstanceVar) hlsInstanceVar.destroy();

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
    hls.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) console.error("HLS Fatal Error:", data);
    });
    return hls;
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
  showTrackRating.value = false;
  trackRatingMessage.value = '';
  await nextTick();

  activeVideo.value = group.video;

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

  if (activeVideo.value && activeVideo.value.qualities?.length > 0) {
    let matchedQuality = null;
    if (props.lastQuality) {
      matchedQuality = activeVideo.value.qualities.find(q => q.label === props.lastQuality);
    }
    if (matchedQuality) {
      activeVideo.value.active_path = matchedQuality.storage_path;
    } else if (!activeVideo.value.active_path) {
      activeVideo.value.active_path = activeVideo.value.qualities[0].storage_path;
    }
  }

  if (activeAudio.value && !activeAudio.value.active_path && activeAudio.value.qualities?.length > 0) {
    activeAudio.value.active_path = activeAudio.value.qualities[0].storage_path;
  }

  if (activeVideo.value?.type === 'VIDEO') startSyncEngine();
  else stopSyncEngine();
};

watch(videoRef, (newEl) => {
  if (newEl && activeVideo.value && activeVideo.value.type === 'VIDEO') {
    hlsVideo = initHls(newEl, activeVideo.value, hlsVideo, true);
    newEl.volume = volume.value;
    newEl.muted = isMuted.value;
    newEl.playbackRate = playbackRate.value;
    newEl.load();
  }
});

watch(audioRef, (newEl) => {
  if (newEl && activeAudio.value) {
    hlsAudio = initHls(newEl, activeAudio.value, hlsAudio, false);
    newEl.volume = volume.value;
    newEl.muted = isMuted.value;
    newEl.playbackRate = playbackRate.value;
    newEl.load();
  }
});

const selectAudioById = async (audioId) => {
  if (audioId === 'original') await selectAudio(null);
  else {
    const audio = currentGroupAudios.value.find(a => a.id === audioId);
    if (audio) await selectAudio(audio);
  }
};

const selectAudio = async (audioSource) => {
  const cTime = videoRef.value.currentTime;
  const isP = !videoRef.value.paused;

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
    audioRef.value.volume = volume.value;
    audioRef.value.muted = isMuted.value;
    audioRef.value.playbackRate = playbackRate.value;
  } else if (hlsAudio) {
    hlsAudio.destroy();
    hlsAudio = null;
  }

  videoRef.value.currentTime = cTime;
  if (isP) videoRef.value.play();
};

const changeVideoQuality = async (path) => {
  if (!activeVideo.value || activeVideo.value.active_path === path) return;
  const cTime = videoRef.value.currentTime;
  const isP = videoRef.value.paused;
  activeVideo.value.active_path = path;
  hlsVideo = initHls(videoRef.value, activeVideo.value, hlsVideo, true);
  videoRef.value.playbackRate = playbackRate.value;
  videoRef.value.currentTime = cTime;
  if (!isP) videoRef.value.play().catch(e => console.warn(e));
  showSettingsMenu.value = false;
};

const changePlaybackRate = (rate) => {
  playbackRate.value = rate;
  if (videoRef.value) videoRef.value.playbackRate = rate;
  if (audioRef.value) audioRef.value.playbackRate = rate;
  showSettingsMenu.value = false;
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
  if (Math.abs(audio.currentTime - targetAudioTime) > 0.2) {
    audio.currentTime = targetAudioTime;
  }
  if (audio.paused) audio.play().catch(e => console.warn(e));
};

const startSyncEngine = () => {
  stopSyncEngine();
  syncInterval = setInterval(performSync, 250);
};

const stopSyncEngine = () => {
  if (syncInterval) clearInterval(syncInterval);
};

const togglePlay = () => {
  if (!videoRef.value) return;
  if (videoRef.value.paused) videoRef.value.play();
  else videoRef.value.pause();
};

const toggleFullscreen = () => {
  if (!document.fullscreenElement) wrapperRef.value.requestFullscreen().catch(err => console.error(err));
  else document.exitFullscreen();
};

const skip = (seconds) => {
  if (videoRef.value) {
    videoRef.value.currentTime += seconds;
    performSync();
  }
};

const onProgressClick = (e) => {
  if (!progressRef.value || !videoRef.value || !duration.value) return;
  const rect = progressRef.value.getBoundingClientRect();
  const pos = (e.clientX - rect.left) / rect.width;
  videoRef.value.currentTime = pos * duration.value;
  performSync();
};

const handleVolumeChange = (e) => {
  const val = parseFloat(e.target.value);
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

const onTimeUpdate = () => {
  if (videoRef.value) currentTime.value = videoRef.value.currentTime;
};
const onLoadedMetadata = () => {
  if (videoRef.value) duration.value = videoRef.value.duration;
};
const onPlay = () => {
  isPlaying.value = true;
  resetControlsTimer();
};
const onPause = () => {
  isPlaying.value = false;
  showControls.value = true;
  if (audioRef.value) audioRef.value.pause();
};

const handleFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement;
};

const goToNextEpisode = () => {
  if (nextEpisodeId.value) {
    window.location.href = `/watch/episode/${nextEpisodeId.value}/`;
  }
};

// --- Оценка озвучки (Track Group) ---
const rateTrackGroup = async (score) => {
  if (trackRatingSubmitting.value || !activeGroupId.value) return;
  trackRatingSubmitting.value = true;
  trackRatingMessage.value = '';
  try {
    const res = await fetch(`/api/v1/player/rate-track/${activeGroupId.value}/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': props.csrfToken},
      body: JSON.stringify({score})
    });
    if (res.ok) {
      showTrackRating.value = false;
      trackRatingMessage.value = 'Rated!';
      setTimeout(() => trackRatingMessage.value = '', 3000);
    } else {
      trackRatingMessage.value = 'Error';
    }
  } catch (e) {
    trackRatingMessage.value = 'Error';
  } finally {
    trackRatingSubmitting.value = false;
  }
};

// --- Телеметрия ---
const sendTelemetry = async () => {
  if (!videoRef.value || isNaN(videoRef.value.duration)) return;
  const currentMs = Math.floor(videoRef.value.currentTime * 1000);
  const dur = videoRef.value.duration || 0;
  const isCompleted = dur > 0 && (videoRef.value.currentTime / dur) > 0.95;
  const tGroupId = parseInt(activeGroupId.value);

  let currentQualityLabel = null;
  if (activeVideo.value && activeVideo.value.qualities) {
    const q = activeVideo.value.qualities.find(q => q.storage_path === activeVideo.value.active_path);
    if (q) currentQualityLabel = q.label;
  }
  const currentAudioAssetId = activeAudio.value ? activeAudio.value.asset_id : null;

  try {
    await fetch('/api/v1/player/telemetry/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': props.csrfToken},
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
  }
};

const startTelemetry = () => {
  if (telemetryInterval) clearInterval(telemetryInterval);
  telemetryInterval = setInterval(() => {
    if (videoRef.value && !videoRef.value.paused) sendTelemetry();
  }, 10000);
};

const stopTelemetry = () => {
  if (telemetryInterval) clearInterval(telemetryInterval);
};

onMounted(() => {
  fetchManifest();
  startTelemetry();
  document.addEventListener('fullscreenchange', handleFullscreenChange);
});

onBeforeUnmount(() => {
  stopSyncEngine();
  stopTelemetry();
  sendTelemetry();
  document.removeEventListener('fullscreenchange', handleFullscreenChange);
  if (hlsVideo) hlsVideo.destroy();
  if (hlsAudio) hlsAudio.destroy();
});

const currentGroupAudios = computed(() => {
  return activeGroupId.value && groupedSources.value[activeGroupId.value]
      ? groupedSources.value[activeGroupId.value].audios : [];
});
</script>

<template>
  <div class="relative w-full h-full aspect-video bg-black rounded-xl overflow-hidden group select-none"
       ref="wrapperRef"
       @mousemove="resetControlsTimer"
       @mouseleave="handleMouseLeave">

    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>
    <div v-else-if="error"
         class="absolute inset-0 flex flex-col items-center justify-center bg-black text-gray-400 z-20">
      <span class="text-lg font-bold">{{ error }}</span>
    </div>

    <div v-else class="w-full h-full">
      <video
          v-if="activeVideo && activeVideo.type === 'VIDEO'"
          ref="videoRef"
          class="w-full h-full cursor-pointer"
          playsinline
          crossorigin="anonymous"
          :muted="!!activeAudio || isMuted"
          @click="togglePlay"
          @dblclick="toggleFullscreen"
          @timeupdate="onTimeUpdate"
          @loadedmetadata="onLoadedMetadata"
          @play="onPlay"
          @pause="onPause"
          @seeking="performSync"
          @waiting="performSync"
      ></video>

      <iframe
          v-else-if="activeVideo && activeVideo.type === 'EXTERNAL_PLAYER'"
          :src="activeVideo.storage_path"
          class="w-full h-full border-0"
          allowfullscreen
          allow="autoplay; encrypted-media"
      ></iframe>

      <audio v-if="activeAudio" ref="audioRef" class="hidden" preload="auto"></audio>
    </div>

    <!-- Кнопка Next Episode (появляется за 15 сек до конца) -->
    <button v-if="nextEpisodeId && duration && (duration - currentTime <= 15) && duration > 0"
            @click="goToNextEpisode"
            class="absolute bottom-24 right-4 bg-brand hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg shadow-2xl transition-transform hover:scale-105 z-30 pointer-events-auto flex items-center gap-2">
      <span>Next Episode</span>
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7"></path>
      </svg>
    </button>

    <!-- Custom Controls Overlay -->
    <div v-if="activeVideo && activeVideo.type === 'VIDEO'"
         class="absolute inset-0 flex flex-col justify-between transition-opacity duration-300 pointer-events-none z-20"
         :class="showControls ? 'opacity-100' : 'opacity-0'">

      <!-- Top Bar: Audio, Track Group & Rating -->
      <div
          class="p-4 bg-gradient-to-b from-black/80 to-transparent flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        <div v-if="currentGroupAudios.length > 0"
             class="pointer-events-auto flex items-center bg-gray-900/80 border border-gray-700 rounded shadow-lg backdrop-blur">
          <div class="px-3 py-1.5 text-xs font-bold text-gray-400 uppercase tracking-wider border-r border-gray-700">
            Audio
          </div>
          <select
              class="bg-transparent text-white text-sm font-semibold outline-none px-2 py-1.5 cursor-pointer appearance-none"
              @change="e => selectAudioById(e.target.value)">
            <option value="original" class="bg-gray-900">Original</option>
            <option v-for="a in currentGroupAudios" :key="a.id" :value="a.id" class="bg-gray-900"
                    :selected="activeAudio?.id === a.id">
              {{ a.meta_info?.language || 'Dub' }}
            </option>
          </select>
        </div>

        <div
            class="pointer-events-auto flex items-center bg-gray-900/80 border border-gray-700 rounded shadow-lg backdrop-blur relative">
          <div class="px-3 py-1.5 text-xs font-bold text-gray-400 uppercase tracking-wider border-r border-gray-700">
            Version
          </div>
          <select v-model="activeGroupId" @change="selectGroup(activeGroupId)"
                  class="bg-transparent text-white text-sm font-semibold outline-none px-2 py-1.5 cursor-pointer appearance-none max-w-[200px] truncate">
            <option v-for="(group, id) in groupedSources" :key="id" :value="id" class="bg-gray-900">{{
                group.title
              }}
            </option>
          </select>

          <!-- Оценка Озвучки (Track Rating) -->
          <div class="border-l border-gray-700 px-2 flex items-center">
            <button @click="showTrackRating = !showTrackRating"
                    class="text-yellow-500 hover:scale-125 transition-transform" title="Rate this version">
              <svg class="w-5 h-5 drop-shadow" fill="currentColor" viewBox="0 0 20 20">
                <path
                    d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
              </svg>
            </button>
            <div v-if="showTrackRating"
                 class="absolute top-full right-0 mt-2 bg-gray-900 border border-gray-700 p-2 rounded shadow-xl flex items-center gap-1 z-50"
                 @mouseleave="showTrackRating = false">
              <button v-for="s in 10" :key="s" @mouseenter="hoverTrackScore = s" @mouseleave="hoverTrackScore = 0"
                      @click="rateTrackGroup(s)" class="text-gray-500 hover:text-yellow-500 transition-colors">
                <svg class="w-5 h-5" :class="{'text-yellow-500': s <= hoverTrackScore}" fill="currentColor"
                     viewBox="0 0 20 20">
                  <path
                      d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
                </svg>
              </button>
            </div>
            <span v-if="trackRatingMessage"
                  class="absolute top-full right-0 mt-12 text-xs font-bold text-brand bg-black/80 px-2 py-1 rounded">{{
                trackRatingMessage
              }}</span>
          </div>
        </div>
      </div>

      <!-- Bottom Bar: Playback Controls -->
      <div
          class="bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-12 pb-4 px-4 w-full pointer-events-auto">

        <div
            class="relative w-full h-1.5 bg-gray-600/50 rounded-full mb-4 cursor-pointer hover:h-2 transition-all group/prog"
            ref="progressRef" @click="onProgressClick">
          <div class="absolute top-0 left-0 h-full bg-brand rounded-full relative"
               :style="{ width: duration ? (currentTime / duration * 100) + '%' : '0%' }">
            <div
                class="absolute right-0 top-1/2 transform -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow scale-0 group-hover/prog:scale-100 transition-transform"></div>
          </div>
        </div>

        <div class="flex items-center justify-between text-white">
          <div class="flex items-center gap-4">
            <button @click="togglePlay" class="hover:text-brand transition transform hover:scale-110">
              <svg v-if="!isPlaying" class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 4l12 6-12 6z"></path>
              </svg>
              <svg v-else class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z"
                      clip-rule="evenodd"></path>
              </svg>
            </button>
            <button @click="skip(-10)" class="text-gray-300 hover:text-white transition" title="Rewind 10s">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.333 4zM4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z"></path>
              </svg>
            </button>
            <button @click="skip(10)" class="text-gray-300 hover:text-white transition" title="Skip 10s">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M11.933 12.8a1 1 0 000-1.6L6.6 7.2A1 1 0 005 8v8a1 1 0 001.6.8l5.333-4zM19.933 12.8a1 1 0 000-1.6l-5.334-4A1 1 0 0013 8v8a1 1 0 001.6.8l5.334-4z"></path>
              </svg>
            </button>

            <div class="flex items-center gap-2 group/vol relative">
              <button @click="toggleMute" class="text-gray-300 hover:text-white transition">
                <svg v-if="isMuted || volume === 0" class="w-6 h-6" fill="none" stroke="currentColor"
                     viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"></path>
                </svg>
                <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"></path>
                </svg>
              </button>
              <input type="range" min="0" max="1" step="0.05" :value="isMuted ? 0 : volume" @input="handleVolumeChange"
                     class="w-0 opacity-0 group-hover/vol:w-20 group-hover/vol:opacity-100 transition-all duration-300 cursor-pointer accent-brand">
            </div>

            <div class="text-sm font-semibold text-gray-300 ml-2 font-mono">
              {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
            </div>
          </div>

          <div class="flex items-center gap-4 relative">
            <div class="relative" @mouseleave="showSettingsMenu = false">
              <button @click="showSettingsMenu = !showSettingsMenu"
                      class="text-gray-300 hover:text-white transition p-1" title="Settings">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
              </button>

              <div v-if="showSettingsMenu"
                   class="absolute bottom-full right-0 mb-4 w-48 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden z-50">
                <!-- Speed -->
                <div class="px-4 py-2 text-xs font-bold text-gray-500 uppercase tracking-widest bg-black/50">Speed</div>
                <div class="flex justify-between px-3 py-2 border-b border-gray-800">
                  <button v-for="r in [0.5, 1, 1.25, 1.5, 2]" :key="r" @click="changePlaybackRate(r)"
                          class="px-1.5 py-1 text-xs rounded transition-colors font-bold"
                          :class="playbackRate === r ? 'bg-brand text-white' : 'text-gray-400 hover:text-white'">
                    {{ r }}x
                  </button>
                </div>

                <!-- Quality -->
                <div class="px-4 py-2 text-xs font-bold text-gray-500 uppercase tracking-widest bg-black/50">Quality
                </div>
                <button v-for="q in activeVideo.qualities" :key="q.variant_id"
                        @click="changeVideoQuality(q.storage_path)"
                        class="w-full text-left px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition flex items-center justify-between">
                  {{ q.label }}
                  <svg v-if="activeVideo.active_path === q.storage_path" class="w-4 h-4 text-brand" fill="none"
                       stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                </button>
              </div>
            </div>

            <button @click="toggleFullscreen" class="text-gray-300 hover:text-white transition p-1" title="Fullscreen">
              <svg v-if="!isFullscreen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>
              </svg>
              <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M4 14h6m0 0v6m0-6l-7 7m17-11h-6m0 0V4m0 6l7-7M4 10h6m0 0V4m0 6l-7-7m17 11h-6m0 0v6m0-6l7 7"></path>
              </svg>
            </button>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
select {
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
}

input[type=range] {
  -webkit-appearance: none;
  background: transparent;
}

input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  height: 12px;
  width: 12px;
  border-radius: 50%;
  background: #e50914;
  cursor: pointer;
  margin-top: -4px;
}

input[type=range]::-webkit-slider-runnable-track {
  width: 100%;
  height: 4px;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
}
</style>