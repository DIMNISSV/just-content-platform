<script setup>
import {computed, nextTick, onBeforeUnmount, onMounted, ref, watch} from 'vue';
import Hls from 'hls.js';

import PlayerTopBar from './player/PlayerTopBar.vue';
import PlayerBottomBar from './player/PlayerBottomBar.vue';
import PlayerNextEpisode from './player/PlayerNextEpisode.vue';
import PlayerSkipButton from "./player/PlayerSkipButton.vue";

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
const nextEpisodeId = ref(null);

// State для UI контролов
const isPlaying = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const volume = ref(1);
const isMuted = ref(false);
const showControls = ref(true);
const isFullscreen = ref(false);
const playbackRate = ref(1);

// State для рейтинга озвучки
const trackRatingMessage = ref('');
const trackRatingSubmitting = ref(false);

let hlsVideo = null;
let hlsAudio = null;
let syncInterval = null;
let telemetryInterval = null;
let controlsTimeout = null;

const resetControlsTimer = () => {
  showControls.value = true;
  clearTimeout(controlsTimeout);
  controlsTimeout = setTimeout(() => {
    if (isPlaying.value) {
      showControls.value = false;
    }
  }, 3000);
};

const handleMouseLeave = () => {
  if (isPlaying.value) showControls.value = false;
};

const handleKeyDown = (e) => {
  if (e.target.tagName === 'INPUT') return;

  switch (e.key.toLowerCase()) {
    case ' ':
    case 'k':
      e.preventDefault();
      togglePlay();
      break;
    case 'f':
      e.preventDefault();
      toggleFullscreen();
      break;
    case 'm':
      toggleMute();
      break;
    case 'arrowright':
      skip(10);
      break;
    case 'arrowleft':
      skip(-10);
      break;
  }
};

const handleDoubleClick = (e) => {
  if (!wrapperRef.value) return;

  const rect = wrapperRef.value.getBoundingClientRect();
  const x = e.clientX - rect.left; // Позиция клика относительно левого края плеера
  const width = rect.width;

  if (x < width / 3) {
    skip(-10);
  } else if (x > (width / 3) * 2) {
    skip(10);
  } else {
    toggleFullscreen();
  }
};

const onRateChange = () => {
  if (videoRef.value) {
    const newRate = videoRef.value.playbackRate;
    if (playbackRate.value !== newRate) {
      playbackRate.value = newRate;
      if (audioRef.value) {
        audioRef.value.playbackRate = newRate;
      }
    }
  }
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
};

const changePlaybackRate = (rate) => {
  const newRate = parseFloat(rate);
  if (isNaN(newRate)) return;

  playbackRate.value = newRate;

  if (videoRef.value) {
    videoRef.value.playbackRate = newRate;
  }
  if (audioRef.value) {
    audioRef.value.playbackRate = newRate;
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

const seek = (timeInSeconds) => {
  if (videoRef.value) {
    videoRef.value.currentTime = timeInSeconds;
    performSync();
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
  window.addEventListener('keydown', handleKeyDown);
});

onBeforeUnmount(() => {
  stopSyncEngine();
  stopTelemetry();
  sendTelemetry();
  document.removeEventListener('fullscreenchange', handleFullscreenChange);
  window.removeEventListener('keydown', handleKeyDown);
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
       :class="{ 'cursor-hidden': !showControls && isPlaying }"
       ref="wrapperRef"
       @mousemove="resetControlsTimer"
       @touchstart.passive="resetControlsTimer"
       @mouseleave="handleMouseLeave">

    <!-- Loading & Error States -->
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>
    <div v-else-if="error"
         class="absolute inset-0 flex flex-col items-center justify-center bg-black text-gray-400 z-20">
      <span class="text-lg font-bold">{{ error }}</span>
    </div>

    <!-- Video & Audio Engine -->
    <div v-else class="w-full h-full">
      <video
          v-if="activeVideo && activeVideo.type === 'VIDEO'"
          ref="videoRef"
          class="w-full h-full cursor-pointer"
          playsinline
          crossorigin="anonymous"
          :muted="!!activeAudio || isMuted"
          @click="togglePlay"
          @dblclick="handleDoubleClick"
          @ratechange="onRateChange"
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

    <!-- UI Overlay (Controls) -->
    <div v-if="activeVideo && activeVideo.type === 'VIDEO'"
         class="absolute inset-0 flex flex-col justify-between transition-opacity duration-300 pointer-events-none z-20"
         :class="showControls ? 'opacity-100' : 'opacity-0'">

      <!-- Top Section -->
      <PlayerTopBar
          :grouped-sources="groupedSources"
          :active-group-id="activeGroupId"
          :current-group-audios="currentGroupAudios"
          :active-audio-id="activeAudio?.id"
          :is-submitting-rating="trackRatingSubmitting"
          :rating-message="trackRatingMessage"
          @update:active-group-id="selectGroup"
          @select-audio="selectAudioById"
          @rate-track="rateTrackGroup"
      />

      <PlayerSkipButton
          :current-time="currentTime"
          :duration="duration"
          @skip="seek"
      />

      <!-- Next Episode Popup -->
      <PlayerNextEpisode
          :next-episode-id="nextEpisodeId"
          :duration="duration"
          :current-time="currentTime"
      />

      <!-- Bottom Section -->
      <PlayerBottomBar
          :current-time="currentTime"
          :duration="duration"
          :is-playing="isPlaying"
          :is-muted="isMuted"
          :volume="volume"
          :playback-rate="playbackRate"
          :qualities="activeVideo?.qualities || []"
          :active-quality-path="activeVideo?.active_path"
          :is-fullscreen="isFullscreen"
          @toggle-play="togglePlay"
          @skip="skip"
          @seek="seek"
          @toggle-mute="toggleMute"
          @update:volume="setVolume"
          @update:playback-rate="changePlaybackRate"
          @change-quality="changeVideoQuality"
          @toggle-fullscreen="toggleFullscreen"
      />
    </div>
  </div>
</template>

<style scoped>
/* Прячем курсор, если контролы скрыты и видео проигрывается */
.cursor-hidden {
  cursor: none;
}

/* Плавный переход для оверлея контролов */
.pointer-events-none {
  transition: opacity 0.3s ease;
}
</style>