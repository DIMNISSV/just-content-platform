<script setup>
import {computed} from 'vue';

const props = defineProps({
  nextEpisodeId: {type: String, default: null},
  duration: {type: Number, default: 0},
  currentTime: {type: Number, default: 0}
});

const shouldShow = computed(() => {
  return props.nextEpisodeId && props.duration > 0 && (props.duration - props.currentTime <= 15);
});

const goToNext = () => {
  window.location.href = `/watch/episode/${props.nextEpisodeId}/`;
};
</script>

<template>
  <button v-if="shouldShow" @click="goToNext"
          class="absolute bottom-24 right-4 bg-brand hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg shadow-2xl transition-transform hover:scale-105 z-30 pointer-events-auto flex items-center gap-2">
    <span>Next Episode</span>
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7"></path>
    </svg>
  </button>
</template>