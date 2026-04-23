<script setup>
import {ref, onMounted} from 'vue';
import StreamSelectorModal from './StreamSelectorModal.vue';

const props = defineProps({
  csrfToken: String
});

const rawFiles = ref([]);
const contentTree = ref([]);
const isLoading = ref(true);

// State для дерева
const expandedTitles = ref(new Set());
const expandedEpisodes = ref(new Set());

// State для модального окна
const showStreamModal = ref(false);
const selectedFileForModal = ref(null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const [rawRes, treeRes] = await Promise.all([
      fetch('/api/v1/media/raw-files/'),
      fetch('/api/v1/content/tree/')
    ]);
    const rawData = await rawRes.json();
    rawFiles.value = rawData.results || rawData;
    contentTree.value = await treeRes.json();
  } catch (e) {
    console.error("Failed to fetch wizard data", e);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const toggleTitle = (id) => {
  if (expandedTitles.value.has(id)) expandedTitles.value.delete(id);
  else expandedTitles.value.add(id);
};

const toggleEpisode = (id) => {
  if (expandedEpisodes.value.has(id)) expandedEpisodes.value.delete(id);
  else expandedEpisodes.value.add(id);
};

// Drag-and-Drop логика
const handleDragStart = (e, fileId) => {
  e.dataTransfer.setData('fileId', fileId);
  e.dataTransfer.dropEffect = 'move';
};

const handleDrop = (e, targetId, dropType, targetType, targetName) => {
  e.preventDefault();
  const fileId = e.dataTransfer.getData('fileId');
  if (!fileId) return;

  const file = rawFiles.value.find(f => f.id === fileId);
  if (!file) return;

  // Открываем модальное окно выбора стримов
  selectedFileForModal.value = {
    file: file,
    targetId: targetId,
    dropType: dropType,
    targetType: targetType,
    targetName: targetName
  };

  showStreamModal.value = true;
};

// Подтверждение выбора в модальном окне
const confirmStreamSelection = async (selectedStreams) => {
  const context = selectedFileForModal.value;
  showStreamModal.value = false;
  isLoading.value = true;

  try {
    const res = await fetch('/api/v1/content/assign-file/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({
        raw_file_id: context.file.id,
        target_id: context.targetId,
        drop_type: context.dropType,
        target_type: context.targetType,
        selected_streams: selectedStreams
      })
    });

    if (res.ok) {
      // Обновляем дерево после успешного связывания
      await fetchData();
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to assign streams"));
    }
  } catch (err) {
    console.error(err);
    alert("Network error occurred.");
  } finally {
    isLoading.value = false;
    selectedFileForModal.value = null;
  }
};
</script>

<template>
  <div class="flex h-[80vh] gap-4 text-gray-200 relative">

    <!-- Loader Оверлей для всего визарда -->
    <div v-if="isLoading && !showStreamModal"
         class="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

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
        <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Content Library (Drop Zones)</h3>
      </div>
      <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
        <div v-for="title in contentTree" :key="title.id" class="mb-4">

          <!-- Уровень Тайтла -->
          <div @click="toggleTitle(title.id)"
               class="flex items-center gap-3 p-2 hover:bg-gray-800 rounded cursor-pointer transition-colors bg-gray-800/30">
            <svg class="w-4 h-4 transition-transform text-gray-400" :class="{'rotate-90': expandedTitles.has(title.id)}"
                 fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="font-bold text-lg">{{ title.name }}</span>
            <span class="text-[10px] uppercase border border-gray-700 px-1.5 rounded text-gray-500">{{
                title.type
              }}</span>
          </div>

          <!-- Уровень Эпизодов -->
          <div v-if="expandedTitles.has(title.id)" class="ml-6 mt-2 space-y-2 border-l-2 border-gray-800 pl-4">

            <div v-for="ep in title.episodes" :key="ep.id" class="border border-gray-800 rounded-lg overflow-hidden">
              <div @click="toggleEpisode(ep.id)"
                   class="p-3 text-sm font-bold text-gray-300 hover:bg-gray-800 cursor-pointer flex justify-between bg-black/20">
                <span>S{{ ep.season_number }}E{{ ep.episode_number }}: {{ ep.name || 'Episode' }}</span>
                <span class="text-[10px] text-gray-500 bg-gray-900 px-2 py-0.5 rounded border border-gray-700">{{
                    ep.track_groups?.length || 0
                  }} Versions</span>
              </div>

              <!-- Уровень Версий (TrackGroups) внутри Эпизода -->
              <div v-if="expandedEpisodes.has(ep.id)" class="p-3 space-y-3 bg-gray-900/50">

                <!-- Существующие версии -->
                <div v-for="group in ep.track_groups" :key="group.id"
                     @dragover.prevent
                     @drop="handleDrop($event, group.id, 'existing_group', 'track_group', group.name)"
                     class="p-3 border border-gray-700 rounded bg-gray-800/50 hover:border-blue-500 transition-colors border-dashed relative group/dropzone">

                  <div
                      class="absolute inset-0 bg-blue-500/10 opacity-0 group-hover/dropzone:opacity-100 transition-opacity pointer-events-none"></div>

                  <div class="text-xs font-black uppercase text-gray-400 mb-2 flex justify-between">
                    {{ group.name }}
                    <span class="text-blue-400 opacity-0 group-hover/dropzone:opacity-100 text-[10px]">Drop to add Audio/Subtitles</span>
                  </div>

                  <div class="flex flex-wrap gap-2">
                    <span v-for="asset in group.assets" :key="asset.id"
                          class="text-[10px] font-bold px-2 py-1 rounded border"
                          :class="asset.type === 'VIDEO' ? 'bg-blue-900/30 text-blue-300 border-blue-800' : 'bg-green-900/30 text-green-300 border-green-800'">
                      {{ asset.type }}: {{ asset.name }}
                    </span>
                  </div>
                </div>

                <!-- Зона создания новой версии -->
                <div @dragover.prevent
                     @drop="handleDrop($event, ep.id, 'new_group', 'episode', 'New Version for S' + ep.season_number + 'E' + ep.episode_number)"
                     class="p-4 border-2 border-dashed border-gray-700 rounded text-center text-xs font-bold text-gray-500 hover:border-brand hover:text-brand hover:bg-brand/5 transition-all cursor-pointer">
                  + DROP VIDEO HERE TO CREATE A NEW VERSION
                </div>
              </div>
            </div>

            <div v-if="title.episodes.length === 0" class="text-xs text-gray-600 italic p-2">
              No episodes created yet.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Модальное окно выбора стримов -->
    <StreamSelectorModal
        v-if="showStreamModal && selectedFileForModal"
        :file="selectedFileForModal.file"
        :drop-type="selectedFileForModal.dropType"
        :target-name="selectedFileForModal.targetName"
        @close="showStreamModal = false; selectedFileForModal = null"
        @confirm="confirmStreamSelection"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #374151;
  border-radius: 10px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #4B5563;
}
</style>