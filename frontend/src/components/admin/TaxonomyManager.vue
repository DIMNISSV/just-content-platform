<script setup>
import {ref, onMounted} from 'vue';
import RawTermsList from './taxonomy/RawTermsList.vue';
import TaxonomyTree from './taxonomy/TaxonomyTree.vue';

const props = defineProps({
  csrfToken: {type: String, required: true}
});

const unmappedTerms = ref([]);
const taxonomyItems = ref([]);
const mappings = ref([]);
const isSyncing = ref(false);

const fetchAll = async () => {
  try {
    const [termsRes, itemsRes, mappingsRes] = await Promise.all([
      fetch('/api/v1/taxonomy/raw-terms/?mapped=false'),
      fetch('/api/v1/taxonomy/items/'),
      fetch('/api/v1/taxonomy/mappings/')
    ]);
    unmappedTerms.value = await termsRes.json();
    taxonomyItems.value = await itemsRes.json();
    mappings.value = await mappingsRes.json();
  } catch (error) {
    console.error("Error fetching taxonomy data:", error);
  }
};

const handleDropped = async ({termId, taxonomyItemId}) => {
  try {
    const res = await fetch('/api/v1/taxonomy/mappings/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({
        raw_term: termId,
        taxonomy_item: taxonomyItemId
      })
    });
    if (res.ok) {
      await fetchAll();
    } else {
      console.error("Failed to map term", await res.json());
    }
  } catch (error) {
    console.error("Network error during mapping drop", error);
  }
};

const handleRemoveMapping = async (mappingId) => {
  try {
    const res = await fetch(`/api/v1/taxonomy/mappings/${mappingId}/`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': props.csrfToken
      }
    });
    if (res.ok) {
      await fetchAll();
    }
  } catch (error) {
    console.error("Error removing mapping:", error);
  }
};

const syncPresets = async () => {
  isSyncing.value = true;
  try {
    const res = await fetch('/api/v1/taxonomy/sync-presets/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': props.csrfToken
      }
    });
    if (res.ok) {
      await fetchAll();
    } else {
      const data = await res.json();
      alert('Ошибка при синхронизации пресетов: ' + data.message);
    }
  } catch (error) {
    console.error("Sync preset error:", error);
  } finally {
    isSyncing.value = false;
  }
};

onMounted(() => {
  fetchAll();
});
</script>

<template>
  <div class="flex flex-col gap-6 font-sans text-gray-200">
    <div class="flex justify-between items-center bg-card p-4 rounded-lg border border-gray-800 shadow">
      <div>
        <h3 class="text-xl font-bold text-white">Панель сопоставления</h3>
        <p class="text-xs text-gray-400 mt-1">Организуйте поступающие термины в режиме реального времени.</p>
      </div>
      <button
          @click="syncPresets"
          :disabled="isSyncing"
          class="bg-brand hover:bg-red-700 text-white font-bold py-2 px-4 rounded text-sm transition disabled:opacity-50"
      >
        {{ isSyncing ? 'Синхронизация...' : 'Синхронизировать пресеты' }}
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[75vh]">
      <RawTermsList :terms="unmappedTerms"/>

      <TaxonomyTree
          :taxonomy-items="taxonomyItems"
          :mappings="mappings"
          @dropped="handleDropped"
          @remove-mapping="handleRemoveMapping"
      />
    </div>
  </div>
</template>