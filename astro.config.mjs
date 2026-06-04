import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://princedumonde.fr', // Replace with your actual domain
  trailingSlash: 'never',
  markdown: {
    shikiConfig: {
      theme: 'dark-plus',
    },
  },
});