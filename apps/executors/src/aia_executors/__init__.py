"""AIA step executors.

The worker (``apps/worker``) claims steps and knows nothing about what a step
does; ``tools/layer_check.sh`` forbids it importing repositories, storage or the
project domain. The implementations live here instead, depend on
``aia_worker.executor`` and ``aia_core``, and are registered by step kind through
``AIA_WORKER_EXECUTORS=aia_executors.registry:build_registry``.
"""
