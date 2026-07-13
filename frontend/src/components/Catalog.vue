<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-black mb-6 tracking-tight border-l-4 border-brand pl-3">Catalog</h1>

    <SearchBuilder @search="handleSearch"/>

    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

    <div v-else-if="results.length === 0" class="text-center text-gray-500 py-12">
      No titles match your criteria.
    </div>

    <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
      <a v-for="title in results" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
        <div
            class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative border border-gray-800 hover:border-brand transition">
          <img v-if="title.poster" :src="title.poster" :alt="title.name"
               class="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300">
          <div v-else class="w-full h-full flex items-center justify-center text-gray-700 font-bold text-xl">No Poster
          </div>

          <div
              class="absolute top-2 right-2 bg-black bg-opacity-80 px-2 py-1 rounded text-xs font-bold text-yellow-400">
            ★ {{ Number(title.rating_score).toFixed(1) }}
          </div>
        </div>
        <h3 class="text-sm font-semibold truncate text-gray-200 group-hover:text-white">{{ title.name }}</h3>
        <div class="flex justify-between text-[10px] uppercase font-bold text-gray-500 mt-1">
          <span>{{ title.release_year || "N/A" }}</span>
          <span>{{ title.type }}</span>
        </div>
      </a>
    </div>
  </div>
</template>

<script setup>
import {ref, onMounted} from 'vue';
import SearchBuilder from './catalog/SearchBuilder.vue';

const results = ref([]);
const loading = ref(false);

const handleSearch = async (ast) => {
  loading.value = true;
  try {
    const response = await fetch('/api/v1/content/titles/advanced_search/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({query: ast})
    });
    if (response.ok) {
      const data = await response.json();
      results.value = data.results !== undefined ? data.results : data;
    }
  } catch (e) {
    console.error("Search failed", e);
  } finally {
    loading.value = false;
  }
};

const fetchInitial = async () => {
  loading.value = true;
  try {
    const response = await fetch('/api/v1/content/titles/');
    if (response.ok) {
      const data = await response.json();
      results.value = data.results !== undefined ? data.results : data;
    }
  } catch (e) {
    console.error("Initial load failed", e);
  } finally {
    loading.value = false;
  }
};

const getCsrfToken = () => {
  const match = document.cookie.match(new RegExp('(^| )csrftoken=([^;]+)'));
  if (match) return match[2];
  return '';
};

onMounted(() => {
  fetchInitial();
});
</script>