<script setup>
import {onMounted, ref, watch} from 'vue';

const titles = ref([]);
const genres = ref([]);
const isLoading = ref(false);
const nextUrl = ref(null);

const filters = ref({
  type: '',
  genre: '',
  ordering: '-created_at',
  search: ''
});

let searchTimeout = null;

// Загрузка справочника жанров
const fetchGenres = async () => {
  try {
    const res = await fetch('/api/v1/content/genres/');
    genres.value = await res.json();
  } catch (e) {
    console.error("Failed to load genres", e);
  }
};

// Загрузка контента
const fetchTitles = async (reset = false) => {
  isLoading.value = true;
  try {
    let url = `/api/v1/content/titles/?ordering=${filters.value.ordering}`;

    if (filters.value.type) url += `&type=${filters.value.type}`;
    if (filters.value.genre) url += `&genre=${filters.value.genre}`;
    if (filters.value.search) url += `&search=${encodeURIComponent(filters.value.search)}`;

    if (!reset && nextUrl.value) {
      url = nextUrl.value;
    }

    const res = await fetch(url);
    const data = await res.json();

    if (reset) {
      titles.value = data.results;
    } else {
      titles.value = [...titles.value, ...data.results];
    }
    nextUrl.value = data.next;
  } catch (e) {
    console.error("Failed to load titles", e);
  } finally {
    isLoading.value = false;
  }
};

// Обработка текстового поиска с задержкой (Debounce)
const handleSearch = () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    fetchTitles(true);
  }, 500);
};

// Реактивно следим за изменениями селектов (кроме текста, он обрабатывается отдельно)
watch(() => [filters.value.type, filters.value.genre, filters.value.ordering], () => {
  fetchTitles(true);
});

onMounted(() => {
  fetchGenres();
  fetchTitles(true);
});
</script>

<template>
  <div class="container mx-auto px-4 py-8 flex flex-col md:flex-row gap-8">

    <!-- Сайдбар Фильтров -->
    <aside class="w-full md:w-64 flex-shrink-0">
      <div class="bg-card p-6 rounded-xl border border-gray-800 sticky top-24 space-y-6">
        <h2 class="text-xl font-black tracking-tighter">FILTERS</h2>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Search</label>
          <input v-model="filters.search" @input="handleSearch" type="text" placeholder="Title name..."
                 class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm">
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Type</label>
          <select v-model="filters.type"
                  class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm">
            <option value="">All Types</option>
            <option value="MOVIE">Movies</option>
            <option value="SERIES">TV Series</option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Genre</label>
          <select v-model="filters.genre"
                  class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm">
            <option value="">All Genres</option>
            <option v-for="g in genres" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase mb-2">Sort By</label>
          <select v-model="filters.ordering"
                  class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-brand outline-none text-sm">
            <option value="-created_at">Newest First</option>
            <option value="-rating_score">Top Rated</option>
            <option value="-release_year">Release Year</option>
          </select>
        </div>
      </div>
    </aside>

    <!-- Сетка контента -->
    <main class="flex-grow">
      <!-- Скелетон/Ожидание -->
      <div v-if="isLoading && titles.length === 0" class="flex justify-center py-20">
        <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
      </div>

      <!-- Результаты -->
      <div v-else>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-5 gap-6">
          <a v-for="title in titles" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
            <div class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative">
              <img v-if="title.poster" :src="title.poster" :alt="title.name"
                   class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">
              <div v-else class="w-full h-full flex items-center justify-center text-gray-700 font-bold text-xl">No
                Poster
              </div>
              <div
                  class="absolute top-2 right-2 bg-black bg-opacity-70 px-2 py-1 rounded text-xs font-bold text-yellow-400">
                {{ Number(title.rating_score).toFixed(1) }}
              </div>
            </div>
            <h3 class="text-sm font-semibold truncate text-gray-200 group-hover:text-white">{{ title.name }}</h3>
            <div class="flex justify-between text-xs text-gray-500 mt-1">
              <span>{{ title.release_year || "N/A" }}</span>
              <span>{{ title.type === 'MOVIE' ? 'Movie' : 'Series' }}</span>
            </div>
          </a>
        </div>

        <!-- Пустой результат -->
        <div v-if="titles.length === 0" class="text-center py-20 text-gray-500">
          No titles found matching your filters.
        </div>

        <!-- Кнопка Load More -->
        <div v-if="nextUrl" class="mt-12 flex justify-center">
          <button @click="fetchTitles(false)" :disabled="isLoading"
                  class="bg-gray-800 hover:bg-gray-700 text-white font-bold py-3 px-8 rounded-full border border-gray-700 transition disabled:opacity-50">
            {{ isLoading ? 'Loading...' : 'Load More' }}
          </button>
        </div>
      </div>
    </main>

  </div>
</template>