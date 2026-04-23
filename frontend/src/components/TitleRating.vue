<script setup>
import {ref} from 'vue';

const props = defineProps({
  titleId: {type: String, required: true},
  initialScore: {type: [String, Number], default: 0},
  csrfToken: {type: String, required: true}
});

const currentScore = ref(parseInt(props.initialScore, 10) || 0);
const hoverScore = ref(0);
const isSubmitting = ref(false);
const statusMessage = ref('');

const setHover = (score) => {
  if (!isSubmitting.value) {
    hoverScore.value = score;
  }
};

const clearHover = () => {
  hoverScore.value = 0;
};

const submitRating = async (score) => {
  if (isSubmitting.value) return;

  isSubmitting.value = true;
  statusMessage.value = '';

  try {
    const res = await fetch(`/api/v1/content/titles/${props.titleId}/rate/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': props.csrfToken
      },
      body: JSON.stringify({score})
    });

    if (res.ok) {
      currentScore.value = score;
      statusMessage.value = 'Thanks for your rating!';
      setTimeout(() => statusMessage.value = '', 3000);
    } else {
      const data = await res.json();
      statusMessage.value = data.error || 'Failed to submit rating.';
    }
  } catch (e) {
    console.error(e);
    statusMessage.value = 'Network error.';
  } finally {
    isSubmitting.value = false;
  }
};
</script>

<template>
  <div class="bg-gray-900/50 p-4 rounded-xl border border-gray-800 inline-block">
    <div class="text-xs font-bold text-gray-500 uppercase mb-2 tracking-widest">Rate this title</div>

    <div class="flex items-center gap-1" @mouseleave="clearHover">
      <button
          v-for="star in 10"
          :key="star"
          @mouseenter="setHover(star)"
          @click="submitRating(star)"
          :disabled="isSubmitting"
          class="focus:outline-none transition-transform"
          :class="{ 'transform hover:scale-125': !isSubmitting, 'opacity-50 cursor-not-allowed': isSubmitting }"
      >
        <svg
            class="w-6 h-6 transition-colors duration-200"
            :class="[
            (hoverScore ? star <= hoverScore : star <= currentScore)
              ? 'text-yellow-500 drop-shadow-md'
              : 'text-gray-700'
          ]"
            fill="currentColor"
            viewBox="0 0 20 20"
        >
          <path
              d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"></path>
        </svg>
      </button>

      <div class="ml-4 text-sm font-bold text-gray-400 w-8 text-center">
        {{ hoverScore || currentScore || '-' }}
      </div>
    </div>

    <div v-if="statusMessage" class="text-xs text-brand mt-2 font-bold transition-opacity">
      {{ statusMessage }}
    </div>
  </div>
</template>