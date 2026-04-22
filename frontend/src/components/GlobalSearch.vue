<script setup>
import {onBeforeUnmount, onMounted, ref} from 'vue';

const query = ref('');
const results = ref([]);
const isLoading = ref(false);
const isOpen = ref(false);
const searchContainer = ref(null);

let searchTimeout = null;

// Обработка текстового ввода с Debounce
const onInput = () => {
  clearTimeout(searchTimeout);

  if (query.value.trim().length < 2) {
    results.value = [];
    isOpen.value = false;
    return;
  }

  isOpen.value = true;
  isLoading.value = true;

  searchTimeout = setTimeout(async () => {
    try {
      const res = await fetch(`/api/v1/content/titles/?search=${encodeURIComponent(query.value)}`);
      const data = await res.json();
      results.value = data.results || [];
    } catch (e) {
      console.error("Search failed", e);
    } finally {
      isLoading.value = false;
    }
  }, 400); // Задержка 400мс
};

const clearSearch = () => {
  query.value = '';
  results.value = [];
  isOpen.value = false;
};

// Логика закрытия выпадающего списка при клике "снаружи"
const handleClickOutside = (event) => {
  if (searchContainer.value && !searchContainer.value.contains(event.target)) {
    isOpen.value = false;
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div class="relative w-full" ref="searchContainer">
    <!-- Инпут поиска -->
    <div class="relative">
      <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
        </svg>
      </div>
      <input
          v-model="query"
          @input="onInput"
          @focus="query.length >= 2 ? isOpen = true : null"
          type="text"
          class="w-full bg-gray-900 border border-gray-700 text-white text-sm rounded-full focus:ring-brand focus:border-brand block pl-10 p-2 placeholder-gray-500 transition-colors"
          placeholder="Search movies, series..."
      >
      <!-- Крестик очистки -->
      <button
          v-if="query.length > 0"
          @click="clearSearch"
          class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-white transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>

    <!-- Выпадающий список результатов -->
    <div
        v-show="isOpen"
        class="absolute mt-2 w-full bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden z-50 flex flex-col max-h-[70vh]"
    >
      <!-- Loader -->
      <div v-if="isLoading" class="p-4 flex justify-center">
        <div class="animate-spin rounded-full h-6 w-6 border-t-2 border-brand"></div>
      </div>

      <!-- No Results -->
      <div v-else-if="results.length === 0 && query.length >= 2" class="p-4 text-center text-sm text-gray-500">
        No results found for "{{ query }}"
      </div>

      <!-- Results List -->
      <ul v-else class="overflow-y-auto custom-scrollbar">
        <li v-for="title in results" :key="title.id" class="border-b border-gray-800 last:border-0">
          <a :href="`/watch/${title.id}/`" class="flex items-center gap-4 p-3 hover:bg-gray-800 transition-colors">

            <div class="w-10 h-14 bg-black flex-shrink-0 rounded overflow-hidden">
              <img v-if="title.poster" :src="title.poster" alt="" class="w-full h-full object-cover">
            </div>

            <div class="flex-grow overflow-hidden">
              <h4 class="text-sm font-bold text-white truncate">{{ title.name }}</h4>
              <p class="text-xs text-gray-500 truncate">{{ title.original_name }}</p>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[10px] font-bold bg-gray-800 px-1.5 py-0.5 rounded text-gray-300">
                  {{ title.release_year || 'N/A' }}
                </span>
                <span class="text-[10px] font-bold text-yellow-500 flex items-center gap-0.5">
                  ★ {{ Number(title.rating_score).toFixed(1) }}
                </span>
                <span class="text-[10px] uppercase text-gray-500 font-bold border border-gray-700 px-1 rounded">
                  {{ title.type === 'MOVIE' ? 'Movie' : 'Series' }}
                </span>
              </div>
            </div>
          </a>
        </li>
      </ul>

      <!-- Go to catalog button (optional flow) -->
      <div v-if="results.length > 0" class="p-2 border-t border-gray-800 bg-black/50">
        <a href="/catalog/"
           class="block text-center text-xs font-bold text-brand hover:text-white transition-colors py-1">
          View all in Catalog &rarr;
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 4px;
}
</style>