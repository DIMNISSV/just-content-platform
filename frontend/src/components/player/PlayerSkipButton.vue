<script setup>
import {computed} from 'vue';

const props = defineProps({
  currentTime: {type: Number, default: 0},
  duration: {type: Number, default: 0},
  // В будущем будем получать эти значения из манифеста
  skipEnd: {type: Number, default: 5}
});

const emit = defineEmits(['skip']);

const isVisible = computed(() => {
  return props.currentTime > 2 && props.currentTime < props.skipEnd;
});
</script>

<template>
  <Transition name="fade">
    <button
        v-if="isVisible"
        @click="emit('skip', skipEnd)"
        class="absolute bottom-28 left-8 bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/30 text-white px-6 py-2 rounded-md font-bold transition-all hover:scale-105 flex items-center gap-2 pointer-events-auto z-40"
    >
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path
            d="M4.555 5.168A1 1 0 003 6v8a1 1 0 001.555.832L10 11.202V14a1 1 0 001.555.832l7-4a1 1 0 000-1.664l-7-4A1 1 0 0010 6v2.798L4.555 5.168z"/>
      </svg>
      Skip Intro
    </button>
  </Transition>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>