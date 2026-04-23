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

const handleDragStart = (e, fileId) => {
  e.dataTransfer.setData('fileId', fileId);
  e.dataTransfer.dropEffect = 'move';
};

const handleDrop = async (e, targetId, targetType) => {
  e.preventDefault();
  const fileId = e.dataTransfer.getData('fileId');
  if (!fileId) return;

  // Визуальный фидбек начала загрузки
  isLoading.value = true;

  try {
    const res = await fetch('/api/v1/content/assign-file/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({
        raw_file_id: fileId,
        target_id: targetId,
        target_type: targetType
      })
    });

    if (res.ok) {
      alert("File assigned and extraction started!");
      // Можно пометить файл как использованный локально
      const file = rawFiles.value.find(f => f.id === fileId);
      if (file) file.is_assigned = true;
    } else {
      const err = await res.json();
      alert("Error: " + err.error);
    }
  } catch (err) {
    console.error(err);
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
             draggable="true"
             @dragstart="handleDragStart($event, file.id)"
             class="p-3 bg-gray-800/50 border border-gray-700 rounded hover:border-brand cursor-move transition-colors group"
             :class="{'opacity-40 grayscale': file.is_assigned}"
        >
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
    <div v-for="ep in title.episodes" :key="ep.id" class="ml-6 mt-2 border-l-2 border-gray-800">
      <div @click="toggleEpisode(ep.id)"
           class="p-2 text-sm font-bold text-gray-300 hover:bg-gray-800 cursor-pointer flex justify-between">
        <span>S{{ ep.season_number }}E{{ ep.episode_number }}: {{ ep.name }}</span>
        <span class="text-[10px] text-gray-600">{{ ep.track_groups.length }} Versions</span>
      </div>

      <!-- Список Версий (появляется при клике на эпизод) -->
      <div v-if="expandedEpisodes.has(ep.id)" class="ml-4 p-2 space-y-2 bg-black/20 rounded-b">
        <div v-for="group in ep.track_groups" :key="group.id"
             @dragover.prevent @drop="handleDrop($event, group.id, 'existing_group')"
             class="p-2 border border-gray-700 rounded bg-gray-800/30 hover:border-blue-500 transition-colors">
          <div class="text-xs font-black uppercase text-gray-500 mb-1">{{ group.name }}</div>
          <div class="flex flex-wrap gap-1">
        <span v-for="asset in group.assets" :key="asset.id"
              class="text-[9px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-300 border border-gray-600">
          {{ asset.type }}: {{ asset.name }}
        </span>
          </div>
        </div>

        <!-- Зона создания новой версии -->
        <div @dragover.prevent @drop="handleDrop($event, ep.id, 'new_group')"
             class="p-3 border-2 border-dashed border-gray-800 rounded text-center text-[10px] text-gray-600 hover:border-brand hover:text-brand transition-all">
          + DROP HERE TO CREATE NEW VERSION
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