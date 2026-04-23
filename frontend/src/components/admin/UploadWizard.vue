<script setup>
import {onMounted, ref} from 'vue';

const props = defineProps({
  csrfToken: String
});

const rawFiles = ref([]);
const contentTree = ref([]);
const isLoading = ref(true);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const [rawRes, treeRes] = await Promise.all([
      fetch('/api/v1/media/raw-files/'),
      fetch('/api/v1/content/tree/')
    ]);
    rawFiles.value = (await rawRes.json()).results;
    contentTree.value = await treeRes.json();
  } catch (e) {
    console.error("Failed to fetch wizard data", e);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

// Состояние развернутых веток дерева
const expandedTitles = ref(new Set());
const toggleTitle = (id) => {
  if (expandedTitles.value.has(id)) expandedTitles.value.delete(id);
  else expandedTitles.value.add(id);
};
</script>

<template>
  <div class="flex h-[80vh] gap-4 text-gray-200">
    <!-- Левая колонка: Сырые файлы -->
    <div class="w-1/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
      <div class="p-4 border-b border-gray-800 bg-black/20 flex justify-between items-center">
        <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Raw Files</h3>
        <span class="text-[10px] bg-gray-800 px-2 py-0.5 rounded">{{ rawFiles.length }}</span>
      </div>
      <div class="flex-grow overflow-y-auto p-2 space-y-2 custom-scrollbar">
        <div v-for="file in rawFiles" :key="file.id"
             class="p-3 bg-gray-800/50 border border-gray-700 rounded hover:border-brand cursor-move transition-colors group">
          <div class="text-sm font-medium truncate" :title="file.original_name">{{ file.original_name }}</div>
          <div class="flex justify-between items-center mt-2">
            <span class="text-[10px] text-gray-500">{{ new Date(file.created_at).toLocaleDateString() }}</span>
            <span class="text-[10px] uppercase font-bold"
                  :class="file.status === 'READY' ? 'text-green-500' : 'text-yellow-500'">
              {{ file.status }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Правая колонка: Дерево контента -->
    <div class="w-2/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
      <div class="p-4 border-b border-gray-800 bg-black/20">
        <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Content Library</h3>
      </div>
      <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
        <div v-for="title in contentTree" :key="title.id" class="mb-4">
          <!-- Title Level -->
          <div @click="toggleTitle(title.id)"
               class="flex items-center gap-3 p-2 hover:bg-gray-800 rounded cursor-pointer transition-colors">
            <svg class="w-4 h-4 transition-transform" :class="{'rotate-90': expandedTitles.has(title.id)}" fill="none"
                 stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="font-bold">{{ title.name }}</span>
            <span class="text-[10px] uppercase border border-gray-700 px-1.5 rounded text-gray-500">{{
                title.type
              }}</span>
          </div>

          <!-- Episodes Level -->
          <div v-if="expandedTitles.has(title.id)" class="ml-6 mt-2 space-y-1 border-l-2 border-gray-800 pl-4">
            <div v-for="ep in title.episodes" :key="ep.id"
                 class="p-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 rounded flex justify-between items-center group">
              <span>S{{ ep.season_number }}E{{ ep.episode_number }}: {{ ep.name }}</span>
              <button
                  class="opacity-0 group-hover:opacity-100 text-[10px] bg-brand px-2 py-0.5 rounded text-white font-bold uppercase">
                Assign File
              </button>
            </div>
            <div v-if="title.episodes.length === 0" class="text-xs text-gray-600 italic p-2">
              No episodes created yet.
            </div>
          </div>
        </div>
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
  border-radius: 10px;
}
</style>