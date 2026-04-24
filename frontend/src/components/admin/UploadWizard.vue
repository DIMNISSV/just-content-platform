<script setup>
import {computed, onBeforeUnmount, onMounted, ref} from 'vue';
import StreamSelectorModal from './StreamSelectorModal.vue';

const props = defineProps({
  csrfToken: String
});

const rawFiles = ref([]);
const contentTree = ref([]);
const isLoading = ref(true);

// Поиск и фильтрация
const searchQuery = ref('');

// State для дерева
const expandedTitles = ref(new Set());
const expandedEpisodes = ref(new Set());

// State для модального окна
const showStreamModal = ref(false);
const selectedFileForModal = ref(null);

// State для загрузки файлов с ПК
const isDraggingFile = ref(false);
const fileInput = ref(null);
const activeUploads = ref([]); // Массив объектов: { name, progress, status }
let pollingInterval = null;

const fetchRawFiles = async () => {
  try {
    const res = await fetch('/api/v1/media/raw-files/');
    const data = await res.json();
    rawFiles.value = data.results || data;
  } catch (e) {
    console.error("Failed to fetch raw files", e);
  }
};

const fetchData = async () => {
  isLoading.value = true;
  try {
    await fetchRawFiles();
    const treeRes = await fetch('/api/v1/content/tree/');
    contentTree.value = await treeRes.json();
  } catch (e) {
    console.error("Failed to fetch wizard data", e);
  } finally {
    isLoading.value = false;
  }
};

// Фильтрация дерева (Тайтлов)
const filteredTree = computed(() => {
  if (!searchQuery.value.trim()) return contentTree.value;
  const q = searchQuery.value.toLowerCase();
  return contentTree.value.filter(t =>
      t.name.toLowerCase().includes(q) ||
      (t.original_name && t.original_name.toLowerCase().includes(q))
  );
});

// Запуск поллинга для обновления статусов (ffprobe анализ)
onMounted(() => {
  fetchData();
  pollingInterval = setInterval(() => {
    // Опрашиваем бэкенд, только если есть файлы в процессе анализа
    const needsPolling = rawFiles.value.some(f => f.status === 'PENDING' || f.status === 'ANALYZING');
    if (needsPolling) fetchRawFiles();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollingInterval) clearInterval(pollingInterval);
});

// --- Загрузка файлов (С ПК на Сервер) ---
const uploadFile = (file) => {
  const uploadState = {name: file.name, progress: 0, status: 'uploading'};
  activeUploads.value.push(uploadState);

  const formData = new FormData();
  formData.append('file', file);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/v1/media/raw-files/', true);
  xhr.setRequestHeader('X-CSRFToken', props.csrfToken);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      uploadState.progress = Math.round((e.loaded / e.total) * 100);
    }
  };

  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      uploadState.status = 'done';
      fetchRawFiles(); // Сразу обновляем список слева
      setTimeout(() => {
        activeUploads.value = activeUploads.value.filter(u => u !== uploadState);
      }, 3000); // Убираем плашку прогресса через 3с
    } else {
      uploadState.status = 'error';
    }
  };
  xhr.onerror = () => {
    uploadState.status = 'error';
  };
  xhr.send(formData);
};

const handleOSDrop = (e) => {
  isDraggingFile.value = false;
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    Array.from(e.dataTransfer.files).forEach(uploadFile);
  }
};

const handleFileInputChange = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    Array.from(e.target.files).forEach(uploadFile);
  }
  e.target.value = null;
};

// --- Взаимодействие с деревом ---
const toggleTitle = (id) => {
  if (expandedTitles.value.has(id)) expandedTitles.value.delete(id);
  else expandedTitles.value.add(id);
};

const toggleEpisode = (id) => {
  if (expandedEpisodes.value.has(id)) expandedEpisodes.value.delete(id);
  else expandedEpisodes.value.add(id);
};

const handleDragStart = (e, fileId) => {
  e.dataTransfer.setData('fileId', fileId);
  e.dataTransfer.dropEffect = 'move';
};

const handleAssignDrop = (e, targetId, dropType, targetType, targetName) => {
  e.preventDefault();
  const fileId = e.dataTransfer.getData('fileId');
  if (!fileId) return;

  const file = rawFiles.value.find(f => f.id === fileId);
  if (!file) return;

  selectedFileForModal.value = {
    file: file, targetId: targetId, dropType: dropType, targetType: targetType, targetName: targetName
  };
  showStreamModal.value = true;
};

const confirmStreamSelection = async (selectedStreams) => {
  const context = selectedFileForModal.value;
  showStreamModal.value = false;
  isLoading.value = true;

  try {
    const res = await fetch('/api/v1/content/assign-file/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': props.csrfToken},
      body: JSON.stringify({
        raw_file_id: context.file.id,
        target_id: context.targetId,
        drop_type: context.dropType,
        target_type: context.targetType,
        selected_streams: selectedStreams
      })
    });

    if (res.ok) await fetchData();
    else {
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

    <div v-if="isLoading && !showStreamModal && rawFiles.length === 0"
         class="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-brand"></div>
    </div>

    <!-- Левая колонка: Сырые файлы -->
    <div class="w-1/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
      <div class="p-4 border-b border-gray-800 bg-black/20 flex flex-col gap-3">
        <div class="flex justify-between items-center">
          <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Raw Files</h3>
          <span class="text-[10px] bg-gray-800 px-2 py-0.5 rounded">{{ rawFiles.length }} Total</span>
        </div>

        <!-- Зона загрузки (OS Drop Zone) -->
        <div
            @dragover.prevent="isDraggingFile = true"
            @dragleave.prevent="isDraggingFile = false"
            @drop.prevent="handleOSDrop"
            @click="$refs.fileInput.click()"
            class="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all"
            :class="isDraggingFile ? 'border-brand bg-brand/10' : 'border-gray-700 hover:border-gray-500 hover:bg-gray-800/50'"
        >
          <span class="text-xs text-gray-400 font-bold block pointer-events-none">Drop video files here or click to browse</span>
          <input type="file" ref="fileInput" multiple accept="video/*, audio/*, .mkv" class="hidden"
                 @change="handleFileInputChange">
        </div>
      </div>

      <div class="flex-grow overflow-y-auto p-2 space-y-2 custom-scrollbar">
        <!-- Индикаторы активных загрузок -->
        <div v-if="activeUploads.length > 0" class="space-y-2 mb-3">
          <div v-for="up in activeUploads" :key="up.name" class="p-2 bg-gray-800 rounded border border-gray-700">
            <div class="flex justify-between text-[10px] font-bold text-gray-400 mb-1">
              <span class="truncate w-3/4">{{ up.name }}</span>
              <span :class="{'text-green-500': up.status==='done', 'text-red-500': up.status==='error'}">
                {{ up.status === 'error' ? 'Failed' : up.progress + '%' }}
              </span>
            </div>
            <div class="h-1.5 w-full bg-black rounded-full overflow-hidden">
              <div class="h-full transition-all duration-300"
                   :class="up.status === 'error' ? 'bg-red-600' : 'bg-brand'"
                   :style="{ width: up.progress + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- Список файлов -->
        <div v-for="file in rawFiles" :key="file.id"
             draggable="true"
             @dragstart="handleDragStart($event, file.id)"
             class="p-3 bg-gray-800/50 border border-gray-700 rounded hover:border-brand cursor-move transition-colors group">
          <div class="text-sm font-medium truncate" :title="file.original_name">{{ file.original_name }}</div>
          <div class="flex justify-between items-center mt-2">
            <span class="text-[10px] text-gray-500 font-mono">{{ file.id.substring(0, 8) }}</span>
            <span class="text-[10px] uppercase font-bold"
                  :class="{'text-green-500': file.status === 'READY', 'text-yellow-500': file.status === 'PENDING' || file.status === 'ANALYZING', 'text-red-500': file.status === 'ERROR'}">
              {{ file.status }}
              <span v-if="file.status === 'ANALYZING'" class="inline-block animate-pulse">...</span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Правая колонка: Дерево контента -->
    <div class="w-2/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
      <div class="p-4 border-b border-gray-800 bg-black/20 space-y-3">
        <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Content Library</h3>
        <!-- Поиск / Фильтрация -->
        <input v-model="searchQuery" type="text" placeholder="Search titles by name..."
               class="w-full bg-black border border-gray-700 rounded p-2 text-xs text-white focus:border-brand outline-none transition-colors"/>
      </div>

      <div class="flex-grow overflow-y-auto p-4 custom-scrollbar">
        <div v-if="filteredTree.length === 0" class="text-center text-sm text-gray-500 py-10">
          No titles found matching "{{ searchQuery }}"
        </div>

        <div v-for="title in filteredTree" :key="title.id" class="mb-4">
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

              <!-- Уровень Версий -->
              <div v-if="expandedEpisodes.has(ep.id)" class="p-3 space-y-3 bg-gray-900/50">
                <div v-for="group in ep.track_groups" :key="group.id"
                     @dragover.prevent
                     @drop="handleAssignDrop($event, group.id, 'existing_group', 'track_group', group.name)"
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

                <!-- Создать новую версию -->
                <div @dragover.prevent
                     @drop="handleAssignDrop($event, ep.id, 'new_group', 'episode', 'New Version for S' + ep.season_number + 'E' + ep.episode_number)"
                     class="p-4 border-2 border-dashed border-gray-700 rounded text-center text-xs font-bold text-gray-500 hover:border-brand hover:text-brand hover:bg-brand/5 transition-all cursor-pointer">
                  + DROP VIDEO HERE TO CREATE A NEW VERSION
                </div>
              </div>
            </div>
            <div v-if="title.episodes.length === 0" class="text-xs text-gray-600 italic p-2">No episodes created yet.
            </div>
          </div>
        </div>
      </div>
    </div>

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