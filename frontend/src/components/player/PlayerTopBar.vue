<script setup>
import {ref} from 'vue';

const props = defineProps({
  groupedSources: {type: Object, required: true},
  activeGroupId: {type: [String, Number], default: null},
  currentGroupAudios: {type: Array, default: () => []},
  activeAudioId: {type: String, default: null},
  isSubmittingRating: {type: Boolean, default: false},
  ratingMessage: {type: String, default: ''}
});

const emit = defineEmits(['update:activeGroupId', 'select-audio', 'rate-track']);

const showTrackRating = ref(false);
const hoverTrackScore = ref(0);

const onGroupChange = (e) => {
  emit('update:activeGroupId', e.target.value);
  showTrackRating.value = false;
};

const onAudioChange = (e) => {
  emit('select-audio', e.target.value);
};

const rateTrack = (score) => {
  emit('rate-track', score);
};
</script>

<template>
  <div
      class="p-4 bg-gradient-to-b from-black/80 to-transparent flex flex-col sm:flex-row gap-4 items-start sm:items-center">

    <!-- Audio Selection -->
    <div v-if="currentGroupAudios.length > 0"
         class="pointer-events-auto flex items-center bg-gray-900/80 border border-gray-700 rounded overflow-hidden shadow-lg backdrop-blur">
      <div class="px-3 py-1.5 text-xs font-bold text-gray-400 uppercase tracking-wider border-r border-gray-700">Audio
      </div>
      <select
          class="bg-transparent text-white text-sm font-semibold outline-none px-2 py-1.5 cursor-pointer appearance-none"
          @change="onAudioChange">
        <option value="original" class="bg-gray-900">Original</option>
        <option v-for="a in currentGroupAudios" :key="a.id" :value="a.id" class="bg-gray-900"
                :selected="activeAudioId === a.id">
          {{ a.meta_info?.language || 'Dub' }}
        </option>
      </select>
    </div>

    <!-- Version (Group) Selection -->
    <div
        class="pointer-events-auto flex items-center bg-gray-900/80 border border-gray-700 rounded overflow-hidden shadow-lg backdrop-blur relative">
      <div class="px-3 py-1.5 text-xs font-bold text-gray-400 uppercase tracking-wider border-r border-gray-700">
        Version
      </div>
      <select :value="activeGroupId" @change="onGroupChange"
              class="bg-transparent text-white text-sm font-semibold outline-none px-2 py-1.5 cursor-pointer appearance-none max-w-[200px] truncate">
        <option v-for="(group, id) in groupedSources" :key="id" :value="id" class="bg-gray-900">{{
            group.title
          }}
        </option>
      </select>

      <!-- Track Rating -->
      <div class="border-l border-gray-700 px-2 flex items-center">
        <button @click="showTrackRating = !showTrackRating" class="text-yellow-500 hover:scale-125 transition-transform"
                title="Rate this version">
          <svg class="w-5 h-5 drop-shadow" fill="currentColor" viewBox="0 0 20 20">
            <path
                d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
          </svg>
        </button>
        <div v-if="showTrackRating"
             class="absolute top-full right-0 mt-2 bg-gray-900 border border-gray-700 p-2 rounded shadow-xl flex items-center gap-1 z-50"
             @mouseleave="showTrackRating = false">
          <button v-for="s in 10" :key="s" @mouseenter="hoverTrackScore = s" @mouseleave="hoverTrackScore = 0"
                  @click="rateTrack(s)" :disabled="isSubmittingRating"
                  class="text-gray-500 hover:text-yellow-500 transition-colors disabled:opacity-50">
            <svg class="w-5 h-5" :class="{'text-yellow-500': s <= hoverTrackScore}" fill="currentColor"
                 viewBox="0 0 20 20">
              <path
                  d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
            </svg>
          </button>
        </div>
        <span v-if="ratingMessage"
              class="absolute top-full right-0 mt-12 text-xs font-bold text-brand bg-black/80 px-2 py-1 rounded">{{
            ratingMessage
          }}</span>
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
</style>