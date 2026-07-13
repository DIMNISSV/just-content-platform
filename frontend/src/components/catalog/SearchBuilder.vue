<template>
  <div class="bg-card border border-gray-800 rounded-xl p-4 mb-8">
    <div class="flex justify-between items-center mb-4 border-b border-gray-800 pb-2">
      <h3 class="text-lg font-bold text-gray-200">Advanced Query Builder</h3>
      <div class="flex gap-2">
        <button @click="resetAst"
                class="text-xs bg-gray-800 hover:bg-gray-700 text-white px-3 py-1.5 rounded transition">Reset
        </button>
        <button @click="applySearch"
                class="text-xs bg-brand hover:bg-red-700 text-white font-bold px-4 py-1.5 rounded transition">Search
        </button>
      </div>
    </div>

    <div class="overflow-x-auto pb-4">
      <SearchNode :node="ast" :isRemovable="false" :genres="genres"/>
    </div>
  </div>
</template>

<script setup>
import {onMounted, ref} from 'vue';
import SearchNode from './SearchNode.vue';

const emit = defineEmits(['search']);

const genres = ref([]);
const ast = ref({
  type: 'AND',
  children: []
});

const loadGenres = async () => {
  try {
    const response = await fetch('/api/v1/content/genres/');
    if (response.ok) {
      genres.value = await response.json();
    }
  } catch (e) {
    console.error("Failed to load genres", e);
  }
};

const resetAst = () => {
  ast.value = {type: 'AND', children: []};
  applySearch();
};

const applySearch = () => {
  emit('search', ast.value);
};

onMounted(() => {
  loadGenres();
});
</script>