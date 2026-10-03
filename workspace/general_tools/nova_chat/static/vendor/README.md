# Controller docking dependency
_Last updated: 2026-10-03 10:02:40_

`nova-dock.js` bundles golden-layout **2.6.0** with esbuild **0.25.5**.
`goldenlayout-base.css` is the unmodified CSS from the same package.
The MIT license is in `golden-layout-LICENSE`.

The bundle entry is:

```js
import { GoldenLayout, LayoutConfig } from 'golden-layout';
window.NovaDock = { GoldenLayout, LayoutConfig };
```

To reproduce, install those exact versions in a temporary build directory and run
`esbuild dock-entry.js --bundle --minify --outfile=nova-dock.js`.
Copy the resulting bundle and package CSS here. Node is only a build dependency;
the controller does not require Node or a CDN at runtime.
