<script setup>
import {ref} from 'vue';

const props = defineProps({
  titleId: {type: String, required: true},
  initialState: {type: [Boolean, String], default: false},
  csrfToken: {type: String, required: true}
});

// Convert string 'true' to actual boolean if passed from template
const isFavorite = ref(props.initialState === 'true' || props.initialState === true);
const isLoading = ref(false);

const toggleFavorite = async () => {
  if (isLoading.value) return;
  isLoading.value = true;

  try {
    const res = await fetch(`/api/v1/content/titles/${props.titleId}/toggle-favorite/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      }
    });
    if (res.ok) {
      const data = await res.json();
      isFavorite.value = data.is_favorite;
    }
  } catch (e) {
    console.error("Failed to toggle favorite", e);
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <button
      @click="toggleFavorite"
      :disabled="isLoading"
      class="flex items-center gap-2 px-4 py-1.5 rounded-full font-bold text-sm transition-all border disabled:opacity-50"
      :class="isFavorite ? 'bg-white text-black border-white hover:bg-gray-200' : 'bg-transparent text-white border-gray-600 hover:border-white hover:bg-white/10'"
  >
    <!-- Plus Icon -->
    <svg v-if="!isFavorite" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 4v16m8-8H4"></path>
    </svg>
    <!-- Checkmark Icon -->
    <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clip-rule="evenodd"></path>
    </svg>
    {{ isFavorite ? 'My List' : 'Add to List' }}
  </button>
</template>