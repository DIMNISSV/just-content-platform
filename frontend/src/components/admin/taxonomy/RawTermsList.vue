<script setup>

</script>

<template>
  <script setup>
    import {ref, computed} from 'vue';

    const props = defineProps({
      terms: {type: Array, required: true}
    });

    const searchQuery = ref('');

    const filteredTerms = computed(() => {
      if (!searchQuery.value) return props.terms;
      const lower = searchQuery.value.toLowerCase();
      return props.terms.filter(t =>
          t.name.toLowerCase().includes(lower) ||
          t.source_field.toLowerCase().includes(lower)
      );
    });

    const onDragStart = (e, term) => {
      e.dataTransfer.setData('termId', term.id);
      e.dataTransfer.effectAllowed = 'move';
    };
  </script>

  <template>
    <div class="col-span-1 bg-card rounded-lg border border-gray-800 flex flex-col overflow-hidden shadow">
      <div class="p-4 border-b border-gray-800 bg-gray-900 flex-shrink-0">
        <h4 class="font-bold text-white mb-3">Несопоставленные термины ({{ filteredTerms.length }})</h4>
        <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск сырых терминов..."
            class="w-full bg-black border border-gray-700 rounded p-2 text-sm text-white focus:border-brand outline-none transition"
        />
      </div>
      <div class="flex-grow overflow-y-auto p-4 space-y-2 custom-scrollbar">
        <div v-if="filteredTerms.length === 0" class="text-gray-500 text-sm text-center py-4">
          Несопоставленные термины не найдены.
        </div>
        <div
            v-for="term in filteredTerms"
            :key="term.id"
            draggable="true"
            @dragstart="onDragStart($event, term)"
            class="bg-gray-800 p-3 rounded border border-gray-700 cursor-grab active:cursor-grabbing hover:border-brand transition group"
        >
          <div class="text-sm font-semibold text-white truncate">{{ term.name }}</div>
          <div class="text-[10px] text-brand uppercase font-black tracking-widest mt-1">
            ИСТОЧНИК: {{ term.source_field }}
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
      border-radius: 4px;
    }

    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
      background: #4b5563;
    }
  </style>
</template>

<style scoped>

</style>