/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./templates/**/*.html",
        "./frontend/src/**/*.{vue,js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                brand: '#e50914',
                dark: '#111111',
                card: '#1a1a1a',
            }
        },
    },
    plugins: [],
}