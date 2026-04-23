<script setup>
import {ref, watch} from 'vue';

const props = defineProps({
  currentTime: {type: Number, default: 0},
  duration: {type: Number, default: 0},
  isPlaying: {type: Boolean, default: false},
  isMuted: {type: Boolean, default: false},
  volume: {type: Number, default: 1},
  playbackRate: {type: Number, default: 1},
  qualities: {type: Array, default: () => []},
  activeQualityPath: {type: String, default: ''},
  isFullscreen: {type: Boolean, default: false}
});

const emit = defineEmits([
  'toggle-play', 'skip', 'seek', 'toggle-mute', 'update:volume',
  'update:playbackRate', 'change-quality', 'toggle-fullscreen'
]);

const progressRef = ref(null);
const showSettingsMenu = ref(false);
const localRate = ref(props.playbackRate);

watch(() => props.playbackRate, (newRate) => {
  localRate.value = newRate;
});

const formatTime = (timeInSeconds) => {
  if (isNaN(timeInSeconds)) return '00:00';
  const m = Math.floor(timeInSeconds / 60);
  const s = Math.floor(timeInSeconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const onProgressClick = (e) => {
  if (!progressRef.value || !props.duration) return;
  const rect = progressRef.value.getBoundingClientRect();
  const pos = (e.clientX - rect.left) / rect.width;
  emit('seek', pos * props.duration);
};

const handleCustomRate = () => {
  let val = parseFloat(localRate.value);
  if (isNaN(val)) val = 1;
  if (val < 0.1) val = 0.1;
  if (val > 16) val = 16;
  emit('update:playbackRate', val);
};
</script>

<template>
  <div
      class="bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-12 pb-4 px-4 w-full pointer-events-auto relative">

    <div
        class="relative w-full h-1.5 bg-gray-600/50 rounded-full mb-4 cursor-pointer hover:h-2 transition-all group/prog"
        ref="progressRef" @click="onProgressClick">
      <div class="absolute top-0 left-0 h-full bg-brand rounded-full"
           :style="{ width: duration ? (currentTime / duration * 100) + '%' : '0%' }">
        <div
            class="absolute right-0 top-1/2 transform -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow scale-0 group-hover/prog:scale-100 transition-transform"></div>
      </div>
    </div>

    <div class="flex items-center justify-between text-white">
      <div class="flex items-center gap-4">
        <button @click="emit('toggle-play')" class="hover:text-brand transition transform hover:scale-110">
          <svg v-if="!isPlaying" class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
            <path d="M4 4l12 6-12 6z"/>
          </svg>
          <svg v-else class="w-8 h-8" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z"
                  clip-rule="evenodd"/>
          </svg>
        </button>

        <div class="flex items-center gap-2 group/vol relative">
          <button @click="emit('toggle-mute')" class="text-gray-300 hover:text-white transition">
            <svg v-if="isMuted || volume === 0" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"/>
            </svg>
            <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/>
            </svg>
          </button>
          <input type="range" min="0" max="1" step="0.05" :value="isMuted ? 0 : volume"
                 @input="e => emit('update:volume', parseFloat(e.target.value))"
                 class="w-0 opacity-0 group-hover/vol:w-20 group-hover/vol:opacity-100 transition-all duration-300 cursor-pointer accent-brand">
        </div>

        <div class="text-sm font-semibold text-gray-300 ml-2 font-mono">
          {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
        </div>
      </div>

      <div class="flex items-center gap-4 relative">
        <div class="relative">
          <button @click="showSettingsMenu = !showSettingsMenu" class="text-gray-300 hover:text-white transition p-1">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </button>

          <Transition name="slide-fade">
            <div v-if="showSettingsMenu"
                 class="absolute bottom-full right-0 mb-4 w-52 bg-gray-900/95 border border-gray-700 rounded-lg shadow-2xl overflow-hidden z-50 backdrop-blur-xl"
                 @mouseleave="showSettingsMenu = false">

              <div class="px-4 py-2 text-[10px] font-black text-gray-500 uppercase tracking-widest bg-black/40">Speed
                Control
              </div>
              <div class="p-3 border-b border-gray-800">
                <div class="flex flex-wrap gap-1.5 mb-3">
                  <button v-for="r in [0.5, 1, 1.5, 2]" :key="r"
                          @click="emit('update:playbackRate', r)"
                          class="flex-1 py-1 text-xs rounded font-bold transition-colors"
                          :class="playbackRate === r ? 'bg-brand text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'">
                    {{ r }}x
                  </button>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-[10px] text-gray-500 font-bold uppercase">Custom:</span>
                  <input type="number" step="0.1" min="0.1" max="16"
                         v-model="localRate"
                         @input="handleCustomRate"
                         @keydown.stop
                         class="flex-grow bg-black border border-gray-700 rounded px-2 py-1 text-xs text-white outline-none focus:border-brand">
                </div>
              </div>

              <div class="px-4 py-2 text-[10px] font-black text-gray-500 uppercase tracking-widest bg-black/40">
                Quality
              </div>
              <div class="max-h-48 overflow-y-auto">
                <button v-for="q in qualities" :key="q.variant_id"
                        @click="emit('change-quality', q.storage_path)"
                        class="w-full text-left px-4 py-2.5 text-xs text-gray-300 hover:bg-brand/10 hover:text-white transition flex items-center justify-between border-b border-gray-800/50 last:border-0">
                  {{ q.label }}
                  <svg v-if="activeQualityPath === q.storage_path" class="w-4 h-4 text-brand" fill="none"
                       stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                </button>
              </div>
            </div>
          </Transition>
        </div>

        <button @click="emit('toggle-fullscreen')" class="text-gray-300 hover:text-white transition p-1">
          <svg v-if="!isFullscreen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/>
          </svg>
          <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 14h6m0 0v6m0-6l-7 7m17-11h-6m0 0V4m0 6l7-7M4 10h6m0 0V4m0 6l-7-7m17 11h-6m0 0v6m0-6l7 7"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from, .slide-fade-leave-to {
  transform: translateY(10px);
  opacity: 0;
}

input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
</style>