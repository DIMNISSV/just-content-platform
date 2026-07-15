<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-black mb-6 tracking-tight border-l-4 border-brand pl-3">Каталог</h1>

    <SearchBuilder @search="handleSearch"/>

    <div v-if="loading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

    <div v-else-if="results.length === 0" class="text-center text-gray-500 py-12">
      Произведения, соответствующие вашим критериям, не найдены.
    </div>

    <div v-else>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
        <a v-for="title in results" :key="title.id" :href="`/watch/${title.id}/`" class="group block">
          <div
              class="aspect-[2/3] bg-gray-900 rounded-lg overflow-hidden mb-3 relative border border-gray-800 hover:border-brand/80 transition shadow-md">
            <img v-if="title.poster" :src="title.poster" :alt="title.name"
                 class="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300">
            <div v-else
                 class="w-full h-full flex items-center justify-center text-gray-700 font-bold text-xl bg-gray-950">Нет
              постера
            </div>

            <div
                class="absolute top-2 right-2 bg-black bg-opacity-80 px-2 py-1 rounded text-xs font-bold text-yellow-400">
              * {{ Number(title.rating_score).toFixed(1) }}
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

          <div class="flex justify-between text-[10px] uppercase font-bold text-gray-500 mt-1">
            <span>{{ title.release_year || "-" }}</span>
            <span>{{ title.type === 'MOVIE' ? 'Фильм' : 'Сериал' }}</span>
          </div>
        </a>
      </div>

      <!-- Pagination Block -->
      <div v-if="totalPages > 1"
           class="flex flex-col sm:flex-row items-center justify-between gap-4 mt-12 border-t border-gray-800/80 pt-6">
        <span class="text-xs text-gray-500 font-semibold">
          Показано {{ offset + 1 }}-{{ Math.min(offset + limit, totalCount) }} из {{ totalCount }} произведений
        </span>
        <div class="flex items-center gap-1">
          <button
              @click="prevPage"
              :disabled="currentPage === 1"
              class="px-3 py-1.5 rounded bg-gray-900 border border-gray-800 hover:border-brand/50 hover:text-brand text-xs font-bold transition disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Назад
          </button>

          <button
              v-for="page in displayedPages"
              :key="page"
              @click="goToPage(page)"
              class="w-8 h-8 rounded text-xs font-bold transition"
              :class="currentPage === page ? 'bg-brand text-white' : 'bg-gray-900 border border-gray-800 hover:border-brand/50 text-gray-300 hover:text-white'"
          >
            {{ page }}
          </button>

          <button
              @click="nextPage"
              :disabled="currentPage === totalPages"
              class="px-3 py-1.5 rounded bg-gray-900 border border-gray-800 hover:border-brand/50 hover:text-brand text-xs font-bold transition disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Вперед
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {ref, onMounted, computed} from 'vue';
import SearchBuilder from './catalog/SearchBuilder.vue';

const results = ref([]);
const loading = ref(false);

const limit = ref(20);
const offset = ref(0);
const totalCount = ref(0);
const currentAst = ref(null);

const totalPages = computed(() => Math.ceil(totalCount.value / limit.value));
const currentPage = computed(() => Math.floor(offset.value / limit.value) + 1);

const displayedPages = computed(() => {
  const range = [];
  const current = currentPage.value;
  const total = totalPages.value;
  const maxVisible = 5;

  if (total <= maxVisible) {
    for (let i = 1; i <= total; i++) {
      range.push(i);
    }
  } else {
    let start = Math.max(1, current - 2);
    let end = Math.min(total, current + 2);

    if (current <= 3) {
      end = 5;
    } else if (current >= total - 2) {
      start = total - 4;
    }

    for (let i = start; i <= end; i++) {
      range.push(i);
    }
  }
  return range;
});

const loadPage = async () => {
  loading.value = true;
  try {
    let url = '';
    let method = 'GET';
    const headers = {
      'Content-Type': 'application/json'
    };
    let body = null;

    if (currentAst.value && currentAst.value.children && currentAst.value.children.length > 0) {
      url = `/api/v1/content/titles/advanced_search/?limit=${limit.value}&offset=${offset.value}`;
      method = 'POST';
      headers['X-CSRFToken'] = getCsrfToken();
      body = JSON.stringify({query: currentAst.value});
    } else {
      url = `/api/v1/content/titles/?limit=${limit.value}&offset=${offset.value}`;
    }

    const response = await fetch(url, {method, headers, body});
    if (response.ok) {
      const data = await response.json();
      if (data.results !== undefined) {
        results.value = data.results;
        totalCount.value = data.count || 0;
      } else {
        results.value = data;
        totalCount.value = data.length || 0;
      }
    }
  } catch (e) {
    console.error("Failed to fetch catalog page", e);
  } finally {
    loading.value = false;
  }
};

const handleSearch = (ast) => {
  offset.value = 0;
  currentAst.value = ast;
  loadPage();
};

const fetchInitial = () => {
  offset.value = 0;
  currentAst.value = null;
  loadPage();
};

const goToPage = (page) => {
  offset.value = (page - 1) * limit.value;
  loadPage();
};

const prevPage = () => {
  if (currentPage.value > 1) {
    goToPage(currentPage.value - 1);
  }
};

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    goToPage(currentPage.value + 1);
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