import './style.css';
import {createApp} from 'vue';
import VideoPlayer from './components/VideoPlayer.vue';

document.addEventListener('DOMContentLoaded', () => {
    const playerMount = document.getElementById('vue-player-mount');
    if (playerMount) {
        const app = createApp(VideoPlayer, {
            contentId: playerMount.dataset.contentId,
            contentType: playerMount.dataset.contentType
        });
        app.mount('#vue-player-mount');
    }
});