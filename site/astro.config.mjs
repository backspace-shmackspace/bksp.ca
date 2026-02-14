import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://bksp.ca',
  output: 'static',
  integrations: [tailwind()],
});
