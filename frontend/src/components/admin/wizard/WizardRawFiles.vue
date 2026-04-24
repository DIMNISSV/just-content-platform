<script setup>
import {ref} from 'vue';

const props = defineProps({
  rawFiles: {type: Array, required: true},
  activeUploads: {type: Array, required: true}
});

const emit = defineEmits(['upload-files']);

const isDraggingFile = ref(false);
const fileInput = ref(null);

const handleOSDrop = (e) => {
  isDraggingFile.value = false;
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    emit('upload-files', Array.from(e.dataTransfer.files));
  }
};

const handleFileInputChange = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    emit('upload-files', Array.from(e.target.files));
  }
  e.target.value = null;
};

const handleDragStart = (e, file) => {
  if (file.status !== 'READY') {
    e.preventDefault();
    return;
  }
  e.dataTransfer.setData('fileId', file.id);
  e.dataTransfer.dropEffect = 'move';
};
</script>

<template>
  <div class="w-1/3 bg-gray-900 rounded-lg border border-gray-800 flex flex-col overflow-hidden">
    <div class="p-4 border-b border-gray-800 bg-black/20 flex flex-col gap-3">
      <div class="flex justify-between items-center">
        <h3 class="font-bold uppercase text-xs tracking-widest text-gray-400">Raw Files</h3>
        <span class="text-[10px] bg-gray-800 px-2 py-0.5 rounded">{{ rawFiles.length }} Total</span>
      </div>

      <!-- OS Drop Zone -->
      <div
          @dragover.prevent="isDraggingFile = true"
          @dragleave.prevent="isDraggingFile = false"
          @drop.prevent="handleOSDrop"
          @click="$refs.fileInput.click()"
          class="border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-all"
          :class="isDraggingFile ? 'border-brand bg-brand/10' : 'border-gray-700 hover:border-gray-500 hover:bg-gray-800/50'"
      >
        <span
            class="text-xs text-gray-400 font-bold block pointer-events-none">Drop video files here or click to browse</span>
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
            <div class="h-full transition-all duration-300" :class="up.status === 'error' ? 'bg-red-600' : 'bg-brand'"
                 :style="{ width: up.progress + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Список файлов -->
      <div v-for="file in rawFiles" :key="file.id"
           :draggable="file.status === 'READY'"
           @dragstart="handleDragStart($event, file)"
           class="p-3 bg-gray-800/50 border rounded transition-colors group relative"
           :class="file.status === 'READY' ? 'border-gray-700 hover:border-brand cursor-move' : 'border-gray-800 opacity-60 cursor-not-allowed'">

        <div v-if="file.status !== 'READY'"
             class="absolute inset-0 bg-black/20 z-10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <span class="text-[9px] bg-black px-2 py-1 rounded text-white font-bold">WAIT FOR ANALYSIS</span>
        </div>

        <div class="text-sm font-medium truncate" :title="file.original_name">{{ file.original_name }}</div>
        <div class="flex justify-between items-center mt-2">
          <span class="text-[10px] text-gray-500 font-mono">{{ file.id.substring(0, 8) }}</span>
          <span class="text-[10px] uppercase font-bold flex items-center gap-1"
                :class="{'text-green-500': file.status === 'READY', 'text-yellow-500': file.status === 'PENDING' || file.status === 'ANALYZING', 'text-red-500': file.status === 'ERROR'}">
            {{ file.status }}
            <span v-if="file.status === 'ANALYZING' || file.status === 'PENDING'"
                  class="animate-spin w-3 h-3 border-2 border-yellow-500 border-t-transparent rounded-full inline-block"></span>
          </span>
        </div>
      </div>
    </div>
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
</style>