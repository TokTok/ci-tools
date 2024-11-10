# Continuous integration tool repository

Version: 0.8.1

This repository contains tools for working with the TokTok Haskell
repositories. Its purpose is mainly to centralise the costly building of
external tools like `hlint` and `stylish-haskell`, which otherwise each Travis
build would have to do, itself. We also store some smaller scripts here that
support the Travis builds, so we can reduce duplication between the separate
Travis build configurations.
