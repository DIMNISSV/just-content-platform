<script setup>
import {ref, onMounted} from 'vue';

const recommendations = ref([]);
const isLoading = ref(true);

const fetchRecommendations = async () => {
  try {
    const res = await fetch('/api/v1/content/recommendations/');
    if (res.ok) {
      recommendations.value = await res.json();
    }
  } catch (e) {
    console.error("Failed to load recommendations", e);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchRecommendations);
</script>

<template>
  <div v-if="!isLoading && recommendations.length > 0">
    <h2 class="text-2xl font-bold mb-6 tracking-tight border-l-4 border-yellow-500 pl-3">Recommended for You</h2>

    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
      <a v-for="title in recommendations" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
        <div
            class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative border border-gray-800 hover:border-brand transition">
          <img v-if="title.poster" :src="title.poster" :alt="title.name"
               class="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300">
          <div v-else class="w-full h-full flex items-center justify-center text-gray-700 font-bold text-xl">
            No Poster
          </div>
          <div class="absolute top-2 right-2 bg-black/70 px-2 py-1 rounded text-xs font-bold text-yellow-400">
            ★ {{ Number(title.rating_score).toFixed(1) }}
          </div>
        </div>
        <h3 class="text-sm font-semibold truncate text-gray-200 group-hover:text-white">{{ title.name }}</h3>

        <div class="flex flex-wrap gap-1 mt-1.5 h-4 overflow-hidden">
          <span v-for="t in (title.taxonomy_items || []).filter(i => i.type !== 'TYPE').slice(0, 3)" :key="t.id"
                class="text-[9px] uppercase font-bold border border-gray-700 px-1 rounded truncate max-w-[80px]"
                :class="{
                  'text-blue-400': t.type === 'GENRE',
                  'text-green-400': t.type === 'TAG',
                  'text-purple-400': t.type === 'CATEGORY'
                }">
            {{ t.name }}
          </span>
        </div>

        <div class="flex justify-between text-xs text-gray-500 mt-1">
          <span>{{ title.release_year || "N/A" }}</span>
          <span>{{ title.type === 'MOVIE' ? 'Movie' : 'Series' }}</span>
        </div>
      </a>
    </div>
  </div>
</template>