<a name="v0.8.1"></a>

## v0.8.1 (2025-02-16)

### Release notes

Prod release for ci-tools.

#### Bug Fixes

- Don't erase release candidate's release notes. ([417cb4a4](https://github.com/TokTok/ci-tools/commit/417cb4a41eca3067c885aea95d83503755fb00d8))
- Run release-soon on everything except push. ([8d52ffa9](https://github.com/TokTok/ci-tools/commit/8d52ffa94e12cc23075fde7d19ae86a10fa91c2b))
- Don't run release-soon check on pushes, only pulls. ([138a61e8](https://github.com/TokTok/ci-tools/commit/138a61e8e66b874849a5e5d82c2607280376c664))
- Output a zero-length file when changelog is empty. ([2337240f](https://github.com/TokTok/ci-tools/commit/2337240fb4840361a1c085b6c91476c3f9c27b43))
- **Security:** Don't pass tokens to repo-local code. ([887ba6cf](https://github.com/TokTok/ci-tools/commit/887ba6cf826e0c43013d90e421047a85b17bd75a))

<a name="v0.8.1-rc.1"></a>

## v0.8.1-rc.1 (2025-02-16)

### Release notes

First release of ci-tools made by ci-tools releaser scripts. Release candidate first.

#### Bug Fixes

- Reviewable config was broken. ([73df8058](https://github.com/TokTok/ci-tools/commit/73df8058eaa6bb34a05411e50b27039447355dc5))
- Forcibly trigger CI on automation pull requests. ([4bcdf84b](https://github.com/TokTok/ci-tools/commit/4bcdf84b4bbc9e23c3a5d9fb89cce3a50b8be373))
- Fix self-name detection for real now. ([782a44c9](https://github.com/TokTok/ci-tools/commit/782a44c9cf025a042e6c301ea1bd55a412dc2616))
- Better detect the project's self-name. ([1dd4366b](https://github.com/TokTok/ci-tools/commit/1dd4366beb0652a67095a4bbb10eb32b2f5c0bbd))
- Verify all assets (except signatures and hashes). ([e10da65d](https://github.com/TokTok/ci-tools/commit/e10da65db8cf31bc50d393f8010d078fac4a5eb7))
- Be less qtox-specific. ([6941efe0](https://github.com/TokTok/ci-tools/commit/6941efe0f13a4d436090ad803cffd36c785bbebc))
- Use the version from the tracking issue if available. ([830de610](https://github.com/TokTok/ci-tools/commit/830de6105193836c84e22d226853b900bd570616))
- Clear the correct cache on `clear_cache`. ([63157bd2](https://github.com/TokTok/ci-tools/commit/63157bd203107473d9be3102d960adc9863678ba))
- Checkout ci-tools into `third_party.` ([b85a6de9](https://github.com/TokTok/ci-tools/commit/b85a6de9faabfa1db0b986cfd19a31e9535a4d07))
- Fix screenshotting in appimage build. ([ac355bdc](https://github.com/TokTok/ci-tools/commit/ac355bdcbc2956a1783b43a6c9cff407b84f9986))
- Checkout ci-tools into the correct directory. ([a2e0673b](https://github.com/TokTok/ci-tools/commit/a2e0673b97ce5e83ba77873888de765aefe29709))
- Don't try to upload release artifacts on master builds. ([18266196](https://github.com/TokTok/ci-tools/commit/18266196d7424fafdc1b9b7189073e10c9131ec8))
- Support original-only artifact file name globs. ([fbb1fb4a](https://github.com/TokTok/ci-tools/commit/fbb1fb4af5bd037880392695f3074b43aab7a47e))
- Check out the PR head instead of merge commit in restyled. ([59f72a80](https://github.com/TokTok/ci-tools/commit/59f72a80cf8534dda16baef101d59dd19ddd976e))
- Respect the `local_required` bool. ([b6c16510](https://github.com/TokTok/ci-tools/commit/b6c165106361fa59cfa9f0ba018f4f442bd65e33))
- Actually handle all the cases of versions being available or not. ([40e0b274](https://github.com/TokTok/ci-tools/commit/40e0b2746905475d709860a40a524b89d7fcd1f4))
- Allow milestone to be empty. ([722fce93](https://github.com/TokTok/ci-tools/commit/722fce937d2644f32c4f66097e6990696cb22759))
- Terminate restyled action with error if a patch exists. ([97066a4e](https://github.com/TokTok/ci-tools/commit/97066a4ee3e886e215e337047ffc975a1cddac73))
- It's `git-patch` instead of `patch`. ([3fd551b6](https://github.com/TokTok/ci-tools/commit/3fd551b6d2d7c0b4f298da5ae0b66ad9fa6dd0fb))
- Don't abort the restyled workflow before uploading a patch. ([1587d59d](https://github.com/TokTok/ci-tools/commit/1587d59ddce88445b7e7b147637ad9efc9ac49aa))
- Don't try to restyle submodules. ([5e2f2c85](https://github.com/TokTok/ci-tools/commit/5e2f2c850312de1ad1735df0dbf23bab04e7c880))
- Fix bzl file parser. ([7cd1c326](https://github.com/TokTok/ci-tools/commit/7cd1c32652a13477cc08e1da53367a355621e31e))
- Ignore empty response from github api. ([9618fca1](https://github.com/TokTok/ci-tools/commit/9618fca17dde1ab1e1c8f88f6f5ea39584a4363c))
- Move workflows to workflows toplevel directory. ([541a153d](https://github.com/TokTok/ci-tools/commit/541a153dd71325654faf51be0600cb9a88fb8798))
- Move workflows to .github. ([54e32f1f](https://github.com/TokTok/ci-tools/commit/54e32f1fe11877100c58c189c11e9de591a62909))
- Disable release version check when there's no draft release. ([3a6eb17c](https://github.com/TokTok/ci-tools/commit/3a6eb17c69cb70ff6786309ceb8bde01247a5ee7))
- Don't evaluate BUILD.bazel. ([cdc378fd](https://github.com/TokTok/ci-tools/commit/cdc378fd2bbcb636db0a331e03bf0585b2339ea4))
- Fail the `hackage_upload` script on upload failure. ([0c2126d6](https://github.com/TokTok/ci-tools/commit/0c2126d6a22f551c6430def25d1da327ab628ecc))
- Fix hackage upload URL for package candidates. ([563e21cd](https://github.com/TokTok/ci-tools/commit/563e21cdcf71f5719d370e21f880a5d89b9a4a52))

#### Features

- Show number of release assets verified in the log. ([c0519b1d](https://github.com/TokTok/ci-tools/commit/c0519b1d6610c99d507220399e4f45d51846893e))
- Add PR validation to common prepare workflow. ([13c63859](https://github.com/TokTok/ci-tools/commit/13c63859954b7130d1546a738fcfb6fc37aec66a))
- Make project-name optional, infer from cmake. ([ba24249e](https://github.com/TokTok/ci-tools/commit/ba24249e74723ccaf0ca91a2408381c3be2b1bb6))
- Add release workflow. ([829df801](https://github.com/TokTok/ci-tools/commit/829df801043ef137c1010982033efbcf95589079))
- Add support for multiple distinct artifacts. ([a50c0246](https://github.com/TokTok/ci-tools/commit/a50c0246fc0899bb0e40ce10df685af5cea4c3b3))
- Add support for multi-file generic artifacts. ([f35086cd](https://github.com/TokTok/ci-tools/commit/f35086cddd1dc66a2070b3d936274fe5a43036b1))
- Add the qTox deploy scripts. ([ea26a8ab](https://github.com/TokTok/ci-tools/commit/ea26a8abd893e40c5aef3767d05a82621410ba86))
- Add Qt application deploy workflows. ([e2ce075f](https://github.com/TokTok/ci-tools/commit/e2ce075f41686df0ff281d7c9952fe18b349884d))
- Add `install_apple_cert` tool to ci-tools scripts. ([6012b895](https://github.com/TokTok/ci-tools/commit/6012b8955818aff2d4cc334bb9bb1d677d007d19))
- Add netlify deploy workflow. ([f7477300](https://github.com/TokTok/ci-tools/commit/f747730015e61640d7b8062078bddadfcd92f2f9))
- Add a release-soon workflow to check if we should release soon. ([33ef2fa4](https://github.com/TokTok/ci-tools/commit/33ef2fa41d30619435181bd5ff42cc2365618c10))
- Support toxic's version location. ([510a4114](https://github.com/TokTok/ci-tools/commit/510a4114bab49ceeb171608daf1f34ea7fdad17a))
- Check the PR milestone matches the upcoming draft release. ([81d08966](https://github.com/TokTok/ci-tools/commit/81d08966bc7c32db7b5c9ae923962de4dd9ff42d))
- Upload restyled diff as artifact. ([c248b2c7](https://github.com/TokTok/ci-tools/commit/c248b2c7a1baeb60d2e3bbf9fc467509f60011c7))
- Add release drafter common github action. ([2b74b8d3](https://github.com/TokTok/ci-tools/commit/2b74b8d3c7af26525e43670a651b77e4f7f2f169))
- Add common CI checks to be shared by all repos. ([cc1982dd](https://github.com/TokTok/ci-tools/commit/cc1982dd081eadf2aea460ddaf9bc20f4230763b))
- Support reading from stdin in stylish-haskell-lhs. ([bda2ee47](https://github.com/TokTok/ci-tools/commit/bda2ee47c6d3958dcaa71d87bc57cb48d6e0e981))
- Add support for dpkg-divert'ed stylish-haskell. ([00aec25d](https://github.com/TokTok/ci-tools/commit/00aec25d4e58e720119e4853b8d986dc996b52f8))
- Add Haskell workflows that can be called from other repos. ([cdf1bed0](https://github.com/TokTok/ci-tools/commit/cdf1bed0dc3c6b97c1cb402d649c13a43c0ae939))
- Add `hackage_upload` script used by Haskell GH actions. ([ab8e6d6f](https://github.com/TokTok/ci-tools/commit/ab8e6d6f168a0318f4b3210cc5a4fa71b25b52f9))
- Add `check_release` script, used by other repos. ([19ddbe74](https://github.com/TokTok/ci-tools/commit/19ddbe740f5ea38e64fd0aa1232e03fdd8bc993f))

<a name="v0.8"></a>

## v0.8 (2020-04-08)

<a name="v0.6"></a>

## v0.6 (2020-03-07)

<a name="v0.5"></a>

## v0.5 (2020-03-06)

<a name="v0.4"></a>

## v0.4 (2020-03-05)

<a name="v0.3"></a>

## v0.3 (2018-08-12)

<a name="v0.2"></a>

## v0.2 (2018-08-05)
