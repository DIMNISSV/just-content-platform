<script setup>
import {ref, onMounted} from 'vue';

const history = ref([]);
const isLoading = ref(true);

const fetchHistory = async () => {
  try {
    const res = await fetch('/api/v1/content/history/');
    if (res.ok) {
      history.value = await res.json();
    }
  } catch (e) {
    console.error("Failed to load watch history", e);
  } finally {
    isLoading.value = false;
  }
};

const formatTime = (ms) => {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const getWatchLink = (item) => {
  return item.episode ? `/watch/episode/${item.episode.id}/` : `/watch/${item.title.id}/`;
};

onMounted(fetchHistory);
</script>

<template>
  <div v-if="!isLoading && history.length > 0">
    <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-brand pl-3">Continue Watching</h2>

    <div class="flex overflow-x-auto gap-6 pb-4 custom-scrollbar snap-x">
      <a v-for="item in history" :key="item.id" :href="getWatchLink(item)"
         class="snap-start flex-shrink-0 w-64 group bg-gray-900 rounded-lg overflow-hidden border border-gray-800 hover:border-brand transition-colors relative block">

        <div class="aspect-video relative bg-black">
          <img v-if="item.title.poster" :src="item.title.poster"
               class="w-full h-full object-cover opacity-50 group-hover:opacity-70 transition-opacity">
          <!-- Play Button Overlay -->
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="bg-brand/80 rounded-full p-3 transform group-hover:scale-110 transition-transform shadow-lg">
              <svg class="w-6 h-6 text-white ml-1" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 4l12 6-12 6z"></path>
              </svg>
            </div>
          </div>
          <!-- Time Badge -->
          <div class="absolute bottom-2 right-2 bg-black/80 px-2 py-1 rounded text-xs font-bold text-white">
            Resume at {{ formatTime(item.progress_ms) }}
          </div>
        </div>

        <div class="p-4">
          <h3 class="text-sm font-bold text-white truncate">{{ item.title.name }}</h3>
          <p class="text-xs text-gray-400 mt-1 truncate">
            <template v-if="item.episode">
              S{{ item.episode.season_number }} E{{ item.episode.episode_number }}: {{ item.episode.name || 'Episode' }}
            </template>
            <template v-else>
              Movie
            </template>
          </p>
        </div>
      </a>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #e50914;
}
</style>