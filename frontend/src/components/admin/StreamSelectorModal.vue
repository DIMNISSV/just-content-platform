<script setup>
import {ref, computed} from 'vue';

const props = defineProps({
  file: Object,
  dropType: String, // 'new_group' | 'existing_group'
  targetName: String
});

const emit = defineEmits(['close', 'confirm']);

// Инициализация списка стримов из метаданных
const streams = ref(props.file.metadata.streams.map(s => ({
  ...s,
  selected: false,
  is_video: s.codec_type === 'video',
  custom_language: s.tags?.language || 'RUS',
  offset_ms: 0
})));

const canConfirm = computed(() => {
  const hasVideo = streams.value.some(s => s.selected && s.is_video);
  const hasAny = streams.value.some(s => s.selected);
  if (props.dropType === 'new_group') return hasVideo;
  return hasAny;
});

const submit = () => {
  const selected = streams.value.filter(s => s.selected).map(s => ({
    index: s.index,
    is_video: s.is_video,
    language: s.custom_language,
    offset_ms: s.offset_ms
  }));
  emit('confirm', selected);
};
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
    <div
        class="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">

      <div class="p-6 border-b border-gray-800">
        <h3 class="text-xl font-bold">Assigning to: {{ targetName }}</h3>
        <p class="text-xs text-gray-500 mt-1">File: {{ file.original_name }}</p>
      </div>

      <div class="flex-grow overflow-y-auto p-6 space-y-4">
        <div v-if="dropType === 'new_group'"
             class="p-3 bg-blue-900/20 border border-blue-800/50 rounded text-xs text-blue-200">
          ℹ️ You must select exactly one <strong>Video</strong> stream for a new version.
        </div>

        <div v-for="s in streams" :key="s.index"
             class="flex items-center gap-4 p-3 rounded-lg border transition-colors"
             :class="s.selected ? 'bg-brand/10 border-brand/50' : 'bg-gray-800/50 border-gray-700'">

          <input type="checkbox" v-model="s.selected" class="w-5 h-5 accent-brand">

          <div class="flex-grow">
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-black uppercase px-1.5 py-0.5 rounded"
                    :class="s.is_video ? 'bg-blue-600' : 'bg-green-600'">
                {{ s.codec_type }}
              </span>
              <span class="font-mono text-sm">#{{ s.index }}: {{ s.codec_name }}</span>
            </div>

            <!-- Доп. поля для аудио -->
            <div v-if="s.selected && !s.is_video" class="mt-3 flex gap-4">
              <div class="flex-1">
                <label class="block text-[10px] uppercase font-bold text-gray-500 mb-1">Language</label>
                <input v-model="s.custom_language" type="text"
                       class="w-full bg-black border border-gray-700 rounded p-1.5 text-xs text-white">
              </div>
              <div class="flex-1">
                <label class="block text-[10px] uppercase font-bold text-gray-500 mb-1">Offset (ms)</label>
                <input v-model.number="s.offset_ms" type="number"
                       class="w-full bg-black border border-gray-700 rounded p-1.5 text-xs text-white">
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="p-6 border-t border-gray-800 flex justify-end gap-3 bg-black/20">
        <button @click="emit('close')" class="px-6 py-2 text-sm font-bold text-gray-400 hover:text-white transition">
          Cancel
        </button>
        <button @click="submit" :disabled="!canConfirm"
                class="px-8 py-2 bg-brand disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-bold rounded shadow-lg hover:bg-red-700 transition">
          Confirm Selection
        </button>
      </div>

    </div>
  </div>
</template>