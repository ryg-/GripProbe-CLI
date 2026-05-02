# GripProbe Compatibility Report

## Reproducibility
- Shells: `aider, continue-cli, gptme, opencode`
- Models: `local/MFDoom/deepseek-r1-tool-calling:8b, local/aravhawk/qwen3.5-opus-4.6-text:9b, local/cryptidbleh/gemma4-claude-opus-4.6:latest, local/fredrezones55/qwen3.5-opus:27b, local/fredrezones55/qwen3.5-opus:9b, local/gemma3:12b, local/gemma4:e2b, local/gemma4:e4b, local/gpt-oss:20b, local/granite3-dense:8b-instruct-q6_K, local/granite4:3b, local/ministral-3:8b, local/mistral-nemo:12b, local/mistral-small:24b, local/nemotron-3-nano:4b, local/orieg/gemma3-tools:12b-ft-v2, local/phi3.5:latest, local/qwen2.5:7b, local/qwen3.5:9b, local/qwen3:14b, local/qwen3:8b, local/yi-coder:9b-chat-q5_K_M`
- Formats: `markdown, tool`
- Hardware profile id: `default1`
- Hardware profile spec: [../../../../specs/hardware_profiles.yaml](../../../../specs/hardware_profiles.yaml)

## Cases

| Shell | Model | Backend | Hash | Format | Test | Status | Reason | Trajectory | Invoked | Match | Warmup (s) | Measured (s) |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|
| continue-cli | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Patch File | FAIL |  | clean | no | 0 | 88.241 | 12.29 |
| continue-cli | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Python File Simple | FAIL |  | clean | no | 0 | 5.074 | 4.774 |
| continue-cli | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell Date | FAIL |  | clean | no | 0 | 5.027 | 4.524 |
| continue-cli | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell PWD | FAIL |  | clean | no | 0 | 4.523 | 4.727 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 1.968 | 1.868 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.219 | 2.37 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.269 | 2.069 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.219 | 2.221 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | markdown | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.069 | 2.068 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | markdown | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.168 | 2.068 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | markdown | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.118 | 2.671 |
| continue-cli | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | markdown | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.419 | 2.219 |
| continue-cli | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | markdown | Patch File | FAIL |  | clean | no | 0 | 63.692 | 14.093 |
| continue-cli | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 8.582 | 8.181 |
| continue-cli | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 7.881 | 8.282 |
| continue-cli | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 8.683 | 8.632 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.369 | 2.469 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.369 | 2.37 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.224 | 2.42 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.219 | 2.419 |
| continue-cli | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Patch File | FAIL |  | clean | no | 0 | 192.014 | 345.748 |
| continue-cli | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Python File Simple | FAIL |  | clean | no | 0 | 83.883 | 56.676 |
| continue-cli | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Shell Date | PASS |  | clean | yes | 100 | 133.585 | 133.531 |
| continue-cli | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Shell PWD | PASS |  | clean | yes | 100 | 133.133 | 133.885 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File | FAIL |  | clean | no | 0 | 91.246 | 27.37 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Simple | FAIL |  | clean | no | 0 | 15.646 | 13.843 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date | FAIL |  | clean | no | 0 | 11.938 | 10.637 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 9.332 | 9.384 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Patch File | FAIL | answered without invoking tool | clean | no | 0 | 27.968 | 21.958 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Python File Simple | FAIL |  | clean | no | 0 | 14.945 | 14.244 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 9.333 | 9.183 |
| continue-cli | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 9.584 | 9.533 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Patch File | PASS |  | recovered | yes | 100 | 42.346 | 6.928 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Simple | PASS |  | recovered | yes | 100 | 10.985 | 11.136 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date | PASS |  | recovered | yes | 100 | 11.988 | 11.237 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell PWD | PASS |  | recovered | yes | 100 | 7.128 | 7.48 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Patch File | TIMEOUT |  | clean | yes | 0 | 120.01 | 120.009 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Simple | PASS |  | recovered | yes | 100 | 40.347 | 42.551 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date | PASS |  | recovered | yes | 100 | 36.187 | 36.839 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell PWD | PASS |  | recovered | yes | 100 | 63.691 | 52.168 |
| gptme | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Patch File | NO_TOOL_CALL |  | recovered | maybe | 0 | 58.033 | 41.797 |
| gptme | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Python File Simple | NO_TOOL_CALL |  | recovered | maybe | 0 | 16.496 | 24.061 |
| gptme | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell Date | NO_TOOL_CALL |  | clean | no | 0 | 19.552 | 19.303 |
| gptme | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell PWD | NO_TOOL_CALL |  | clean | no | 0 | 12.189 | 12.139 |
| gptme | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | tool | Patch File | NO_TOOL_CALL |  | clean | maybe | 0 | 80.38 | 29.077 |
| gptme | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | tool | Python File Simple | NO_TOOL_CALL | answered without invoking tool | recovered | no | 0 | 24.62 | 24.819 |
| gptme | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | tool | Shell Date | NO_TOOL_CALL | answered without invoking tool | recovered | no | 0 | 22.311 | 22.212 |
| gptme | local/granite3-dense:8b-instruct-q6_K | ollama | ec258d53940b1e6b291a0d515dc7151de6ab173266c2b0e5e7b11ddaa920ac1e | tool | Shell PWD | NO_TOOL_CALL |  | clean | no | 0 | 25.769 | 24.617 |
| gptme | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.369 | 2.22 |
| gptme | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.623 | 2.32 |
| gptme | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.625 | 2.67 |
| gptme | local/yi-coder:9b-chat-q5_K_M | ollama | d4b375d4e224e9d900e992f3c5c1881f66d5f333ab9d51333eb15d76c45580e5 | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.168 | 2.469 |
| gptme | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.421 | 2.169 |
| gptme | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 1.968 | 2.118 |
| gptme | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.168 | 2.018 |
| gptme | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.421 | 2.771 |
| gptme | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.268 | 2.519 |
| gptme | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.419 | 2.62 |
| gptme | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.519 | 2.972 |
| gptme | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.519 | 2.519 |
| gptme | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Patch File | TIMEOUT |  | clean | yes | 100 | 120.015 | 120.01 |
| gptme | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Python File Simple | TIMEOUT |  | clean | yes | 100 | 120.01 | 120.009 |
| gptme | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell Date | TIMEOUT |  | clean | yes | 100 | 120.01 | 120.01 |
| gptme | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell PWD | TIMEOUT |  | clean | yes | 100 | 120.01 | 120.009 |
| gptme | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Patch File | TIMEOUT |  | clean | yes | 0 | 120.014 | 120.009 |
| gptme | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Python File Simple | TIMEOUT |  | clean | yes | 100 | 120.016 | 120.012 |
| gptme | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Shell Date | TIMEOUT |  | clean | yes | 100 | 120.368 | 120.662 |
| gptme | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 120.01 | 120.009 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File | NO_TOOL_CALL |  | clean | maybe | 0 | 77.582 | 37.645 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Simple | PASS |  | recovered | yes | 100 | 27.525 | 27.673 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date | PASS |  | recovered | yes | 100 | 32.333 | 32.334 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell PWD | PASS |  | recovered | yes | 100 | 35.337 | 34.738 |
| gptme | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Patch File | NO_TOOL_CALL |  | clean | maybe | 0 | 28.072 | 9.684 |
| gptme | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Simple | NO_TOOL_CALL |  | clean | no | 0 | 10.986 | 11.287 |
| gptme | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell Date | NO_TOOL_CALL |  | clean | no | 0 | 13.096 | 12.192 |
| gptme | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell PWD | NO_TOOL_CALL |  | recovered | maybe | 0 | 12.55 | 10.888 |
| gptme | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Patch File | TIMEOUT |  | clean | yes | 0 | 120.024 | 120.014 |
| gptme | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Python File Simple | TIMEOUT |  | clean | yes | 100 | 120.01 | 120.026 |
| gptme | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Shell Date | TIMEOUT |  | clean | yes | 100 | 120.559 | 120.801 |
| gptme | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Shell PWD | NO_TOOL_CALL |  | clean | no | 0 | 106.896 | 73.518 |
| aider | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Patch File | PASS |  | clean | maybe | 100 | 41.055 | 10.136 |
| aider | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 33.188 | 7.279 |
| aider | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 32.486 | 7.43 |
| aider | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 32.637 | 7.33 |
| aider | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Patch File | PASS |  | clean | maybe | 100 | 41.054 | 14.447 |
| aider | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Simple | PASS |  | clean | maybe | 100 | 39.352 | 19.658 |
| aider | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 64.959 | 22.012 |
| aider | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 43.513 | 14.145 |
| aider | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | markdown | Patch File | PASS |  | clean | maybe | 100 | 53.438 | 16.3 |
| aider | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | markdown | Python File Simple | FAIL |  | clean | maybe | 0 | 47.972 | 21.312 |
| aider | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | markdown | Shell Date | FAIL |  | clean | maybe | 0 | 46.471 | 20.765 |
| aider | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | markdown | Shell PWD | FAIL |  | clean | maybe | 0 | 45.876 | 17.955 |
| aider | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | markdown | Patch File | PASS |  | clean | maybe | 100 | 24.671 | 7.58 |
| aider | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 19.711 | 8.339 |
| aider | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 20.513 | 6.879 |
| aider | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 19.961 | 8.135 |
| aider | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | markdown | Patch File | FAIL |  | clean | maybe | 0 | 24.872 | 9.438 |
| aider | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | markdown | Python File Simple | FAIL |  | clean | maybe | 0 | 22.013 | 9.086 |
| aider | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | markdown | Shell Date | FAIL |  | clean | maybe | 0 | 39.352 | 38.755 |
| aider | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | markdown | Shell PWD | FAIL |  | clean | maybe | 0 | 53.882 | 54.788 |
| aider | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Patch File | PASS |  | clean | maybe | 100 | 54.188 | 9.535 |
| aider | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Python File Simple | FAIL |  | clean | no | 0 | 52.584 | 8.584 |
| aider | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 52.63 | 8.532 |
| aider | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 51.78 | 8.535 |
| aider | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Patch File | FAIL |  | clean | maybe | 0 | 55.687 | 11.891 |
| aider | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 61.002 | 16.601 |
| aider | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 54.885 | 40.804 |
| aider | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell PWD | FAIL |  | clean | no | 0 | 223.062 | 176.262 |
| aider | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Patch File | FAIL |  | clean | maybe | 0 | 51.381 | 16.754 |
| aider | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Simple | FAIL |  | clean | no | 0 | 52.935 | 15.601 |
| aider | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date | FAIL |  | clean | no | 0 | 54.09 | 15.349 |
| aider | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell PWD | FAIL |  | clean | no | 0 | 52.586 | 17.806 |
| aider | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Patch File | PASS |  | clean | maybe | 100 | 182.827 | 83.607 |
| aider | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Simple | FAIL |  | clean | no | 0 | 130.199 | 36.597 |
| aider | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date | FAIL |  | clean | no | 0 | 131.669 | 38.25 |
| aider | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell PWD | FAIL |  | clean | no | 0 | 140.381 | 47.219 |
| aider | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | markdown | Patch File | PASS |  | clean | maybe | 100 | 152.353 | 14.947 |
| aider | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | markdown | Python File Simple | FAIL |  | clean | no | 0 | 150.953 | 9.734 |
| aider | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | markdown | Shell Date | FAIL |  | clean | no | 0 | 149.148 | 9.435 |
| aider | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 151.106 | 13.895 |
| aider | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Patch File | PASS |  | clean | maybe | 100 | 63.807 | 8.583 |
| aider | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 47.523 | 7.931 |
| aider | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 47.217 | 7.431 |
| aider | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 47.521 | 7.832 |
| aider | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | markdown | Patch File | FAIL |  | clean | maybe | 0 | 39.802 | 8.684 |
| aider | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 37.496 | 7.229 |
| aider | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 40.856 | 6.728 |
| aider | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | markdown | Shell PWD | FAIL |  | clean | maybe | 0 | 38.199 | 7.481 |
| aider | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | markdown | Patch File | PASS |  | clean | maybe | 100 | 26.523 | 9.635 |
| aider | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 23.916 | 10.287 |
| aider | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 24.169 | 8.133 |
| aider | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | markdown | Shell PWD | FAIL |  | clean | maybe | 0 | 23.567 | 7.482 |
| aider | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Patch File | FAIL |  | clean | maybe | 0 | 47.019 | 8.332 |
| aider | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 45.518 | 7.78 |
| aider | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Shell Date | FAIL | answered without invoking tool | clean | no | 0 | 45.619 | 8.031 |
| aider | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | markdown | Shell PWD | FAIL | answered without invoking tool | clean | no | 0 | 46.022 | 8.032 |
| opencode | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Patch File | FAIL |  | clean | maybe | 0 | 49.423 | 12.193 |
| opencode | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 14.802 | 13.294 |
| opencode | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date | FAIL |  | clean | maybe | 0 | 6.628 | 6.981 |
| opencode | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 6.728 | 6.531 |
| opencode | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Patch File | FAIL |  | clean | maybe | 0 | 105.25 | 29.988 |
| opencode | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 34.596 | 59.547 |
| opencode | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date | FAIL |  | clean | maybe | 0 | 21.062 | 11.844 |
| opencode | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 15.498 | 15.65 |
| opencode | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Patch File | FAIL |  | clean | maybe | 0 | 44.515 | 18.505 |
| opencode | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 11.19 | 19.509 |
| opencode | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell Date | FAIL |  | clean | maybe | 0 | 6.981 | 8.886 |
| opencode | local/MFDoom/deepseek-r1-tool-calling:8b | ollama | 3aa3d24e7e624d24402e00afb506d42c9cc3cc86f8df8cd8f937fb474205bbb8 | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 7.63 | 7.387 |
| opencode | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Patch File | FAIL |  | clean | maybe | 0 | 23.019 | 5.676 |
| opencode | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 6.882 | 5.526 |
| opencode | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Shell Date | FAIL |  | clean | maybe | 0 | 4.925 | 5.527 |
| opencode | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 4.974 | 4.826 |
| opencode | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.126 | 3.874 |
| opencode | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.018 | 2.419 |
| opencode | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.319 | 2.319 |
| opencode | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.57 | 3.073 |
| opencode | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.971 | 2.82 |
| opencode | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.623 | 2.671 |
| opencode | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.771 | 2.77 |
| opencode | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.023 | 2.369 |
| opencode | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Patch File | FAIL |  | clean | maybe | 0 | 56.394 | 15.001 |
| opencode | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 53.283 | 13.546 |
| opencode | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell Date | FAIL |  | clean | maybe | 0 | 10.588 | 15.497 |
| opencode | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 13.097 | 11.142 |
| opencode | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Patch File | FAIL |  | clean | maybe | 0 | 113.416 | 62.057 |
| opencode | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 8.985 | 42.461 |
| opencode | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell Date | FAIL |  | clean | maybe | 0 | 19.461 | 15.801 |
| opencode | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 41.706 | 42.662 |
| opencode | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.005 | 120.004 |
| opencode | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 120.003 | 120.003 |
| opencode | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell Date | TIMEOUT |  | clean | no | 0 | 120.005 | 120.019 |
| opencode | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 120.011 | 120.003 |
| opencode | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.004 | 120.004 |
| opencode | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 120.003 | 120.004 |
| opencode | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Shell Date | TIMEOUT |  | clean | no | 0 | 120.004 | 120.004 |
| opencode | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 120.003 | 120.004 |
| opencode | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.004 | 120.003 |
| opencode | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 120.004 | 120.004 |
| opencode | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date | FAIL |  | clean | maybe | 0 | 120.012 | 71.125 |
| opencode | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 16.199 | 17.709 |
| opencode | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Patch File | FAIL |  | clean | maybe | 0 | 45.365 | 11.891 |
| opencode | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 8.835 | 11.993 |
| opencode | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date | FAIL |  | clean | maybe | 0 | 7.129 | 6.428 |
| opencode | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 13.343 | 6.629 |
| opencode | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Patch File | FAIL |  | clean | maybe | 0 | 44.363 | 35.944 |
| opencode | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Simple | FAIL |  | clean | maybe | 0 | 31.685 | 25.069 |
| opencode | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell Date | FAIL |  | clean | maybe | 0 | 19.956 | 28.732 |
| opencode | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell PWD | FAIL |  | clean | maybe | 0 | 19.356 | 20.012 |
| opencode | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.004 | 120.005 |
| opencode | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 120.004 | 120.005 |
| opencode | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Shell Date | TIMEOUT |  | clean | no | 0 | 120.004 | 120.012 |
| opencode | local/orieg/gemma3-tools:12b-ft-v2 | ollama | 13652b120c21fabfd312df93597ac875b0fcd49fe4d3da4d4a703fdabbbd071d | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 120.004 | 120.004 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Patch File From Prepared Patch | FAIL |  | clean | no | 0 | 47.935 | 13.498 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted | FAIL | answered without invoking tool | clean | no | 0 | 5.276 | 5.277 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 5.527 | 6.18 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 5.527 | 5.778 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Save File | PASS |  | clean | yes | 100 | 6.13 | 6.23 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 5.126 | 5.731 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 4.875 | 4.925 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell File | PASS |  | clean | yes | 100 | 5.075 | 5.828 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 63.266 | 62.863 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 27.93 | 19.359 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 23.67 | 16.255 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 22.918 | 24.271 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Save File | PASS |  | clean | yes | 100 | 29.132 | 19.963 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 17.456 | 24.973 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 29.887 | 24.973 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell File | PASS |  | clean | yes | 100 | 16.555 | 25.776 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 58.954 | 16.456 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 8.885 | 9.39 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 7.582 | 8.134 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 9.087 | 7.584 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Save File | FAIL | answered without invoking tool | clean | no | 0 | 11.391 | 16.605 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 7.533 | 9.337 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 6.98 | 7.132 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell File | PASS |  | clean | yes | 100 | 8.184 | 7.033 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Patch File From Prepared Patch | FAIL | answered without invoking tool | clean | no | 0 | 108.52 | 27.631 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 16.303 | 15.0 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 16.453 | 27.781 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 14.749 | 14.699 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Save File | PASS |  | clean | yes | 100 | 13.746 | 25.075 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 12.893 | 14.397 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 12.544 | 13.845 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell File | PASS |  | clean | yes | 100 | 12.943 | 14.799 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Patch File From Prepared Patch | FAIL | answered without invoking tool | clean | no | 0 | 318.698 | 202.34 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 146.921 | 162.695 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 252.918 | 186.735 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 178.491 | 306.458 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Save File | PASS |  | clean | yes | 100 | 167.415 | 122.467 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 139.855 | 168.621 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 170.776 | 127.764 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell File | PASS |  | clean | yes | 100 | 124.21 | 136.339 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Patch File From Prepared Patch | FAIL | answered without invoking tool | clean | no | 0 | 41.914 | 8.534 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 5.326 | 5.477 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 5.929 | 5.327 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 5.577 | 6.082 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Save File | FAIL | answered without invoking tool | clean | no | 0 | 5.878 | 6.279 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 5.327 | 4.826 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 4.624 | 4.976 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell File | PASS |  | clean | yes | 100 | 5.382 | 5.328 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Nonce Proof | FAIL | answered without invoking tool | clean | no | 0 | 16.053 | 19.331 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 45.939 | 18.411 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 8.635 | 10.239 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 16.201 | 8.986 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 11.394 | 10.191 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Save File | FAIL | answered without invoking tool | clean | no | 0 | 11.69 | 9.839 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 9.185 | 7.935 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 10.84 | 12.544 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell File | PASS |  | clean | yes | 100 | 9.638 | 8.636 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Web Nonce Proof | PASS |  | clean | yes | 100 | 7.331 | 20.063 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Patch File From Prepared Patch | FAIL |  | clean | no | 0 | 43.962 | 8.133 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted | FAIL | answered without invoking tool | clean | no | 0 | 5.929 | 5.526 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 5.326 | 5.528 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 5.928 | 5.576 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Save File | FAIL | answered without invoking tool | clean | no | 0 | 6.478 | 6.629 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 4.824 | 5.076 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 5.777 | 4.976 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell File | PASS |  | clean | yes | 100 | 5.125 | 5.378 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Web Nonce Proof | FAIL |  | clean | no | 0 | 9.484 | 6.278 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 87.706 | 37.046 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 74.929 | 47.769 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 23.466 | 22.366 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 17.152 | 33.04 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Save File | PASS |  | clean | yes | 100 | 20.86 | 22.115 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 26.32 | 25.627 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 20.059 | 41.905 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell File | PASS |  | clean | yes | 100 | 23.67 | 17.152 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Web Nonce Proof | FAIL | answered without invoking tool | clean | no | 0 | 57.595 | 195.191 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 57.893 | 13.794 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 7.481 | 7.78 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 9.285 | 7.781 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 8.834 | 7.28 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Save File | FAIL | answered without invoking tool | clean | no | 0 | 16.801 | 7.932 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 8.382 | 7.482 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 6.528 | 8.683 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell File | PASS |  | clean | yes | 100 | 7.181 | 9.435 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Web Nonce Proof | FAIL | answered without invoking tool | clean | no | 0 | 24.618 | 18.206 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Patch File From Prepared Patch | FAIL | answered without invoking tool | clean | no | 0 | 98.997 | 27.682 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 7.681 | 14.648 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 16.903 | 19.256 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 15.148 | 17.001 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Save File | PASS |  | clean | yes | 100 | 7.383 | 17.403 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 12.743 | 16.002 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 13.745 | 11.891 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell File | PASS |  | clean | yes | 100 | 12.091 | 24.271 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Web Nonce Proof | PASS |  | clean | yes | 100 | 381.526 | 43.322 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Patch File From Prepared Patch | FAIL | answered without invoking tool | clean | no | 0 | 245.891 | 126.46 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 147.656 | 223.832 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 171.915 | 176.832 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 208.962 | 153.981 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Save File | PASS |  | clean | yes | 100 | 119.893 | 140.293 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 155.683 | 206.548 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 169.205 | 150.413 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell File | PASS |  | clean | yes | 100 | 125.004 | 131.516 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Web Nonce Proof | PASS |  | clean | yes | 100 | 600.022 | 430.885 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 53.141 | 11.138 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 23.52 | 23.366 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 24.718 | 22.314 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 21.11 | 21.616 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Save File | PASS |  | recovered | yes | 100 | 23.618 | 24.318 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 20.618 | 21.022 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 20.661 | 20.314 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell File | PASS |  | recovered | yes | 100 | 19.106 | 22.015 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Web Nonce Proof | FAIL |  | recovered | yes | 0 | 82.297 | 53.885 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 54.188 | 20.414 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 26.22 | 34.393 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 27.877 | 27.176 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 26.577 | 47.333 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Save File | PASS |  | recovered | yes | 100 | 23.414 | 22.612 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 27.132 | 28.336 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 35.695 | 35.743 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell File | PASS |  | recovered | yes | 100 | 26.087 | 26.029 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Web Nonce Proof | TIMEOUT |  | clean | yes | 0 | 98.444 | 120.011 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Patch File From Prepared Patch | NO_TOOL_CALL |  | clean | maybe | 0 | 47.873 | 10.336 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 12.141 | 12.241 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 13.094 | 13.143 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 10.636 | 11.392 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Save File | PASS |  | recovered | yes | 100 | 7.681 | 8.784 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 10.338 | 10.287 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 9.935 | 10.237 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell File | PASS |  | recovered | yes | 100 | 10.387 | 10.388 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Nonce Proof | PASS |  | recovered | yes | 100 | 18.513 | 18.205 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File From Prepared Patch | FAIL |  | recovered | yes | 0 | 88.262 | 35.446 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 28.327 | 27.978 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Quoted DE | FAIL |  | recovered | yes | 0 | 35.645 | 36.047 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 41.057 | 22.214 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Save File | FAIL |  | recovered | yes | 0 | 17.554 | 17.302 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 38.657 | 76.184 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 66.418 | 37.998 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell File | PASS |  | recovered | yes | 100 | 34.841 | 34.939 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Web Nonce Proof | NO_TOOL_CALL |  | recovered | maybe | 0 | 35.593 | 93.571 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Patch File From Prepared Patch | FAIL |  | recovered | yes | 0 | 49.776 | 15.951 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 16.6 | 16.052 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 12.091 | 12.899 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 12.004 | 10.889 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Save File | PASS |  | recovered | yes | 100 | 9.538 | 9.747 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 14.8 | 12.945 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 10.588 | 10.989 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell File | PASS |  | recovered | yes | 100 | 11.089 | 10.941 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Web Nonce Proof | TIMEOUT |  | recovered | yes | 0 | 36.292 | 120.014 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 74.026 | 42.91 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 65.856 | 91.459 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Quoted DE | TIMEOUT |  | clean | yes | 100 | 46.216 | 120.014 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 54.33 | 54.081 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Save File | PASS |  | recovered | yes | 100 | 26.874 | 49.319 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 49.121 | 45.516 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 52.528 | 47.465 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell File | PASS |  | recovered | yes | 100 | 55.131 | 48.721 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Web Nonce Proof | TIMEOUT |  | recovered | yes | 0 | 72.021 | 120.012 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Patch File | PASS |  | clean | yes | 100 | 38.509 | 8.033 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Python File Simple | PASS |  | clean | yes | 100 | 5.527 | 5.226 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell Date | PASS |  | clean | yes | 100 | 4.626 | 4.876 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Shell PWD | PASS |  | clean | yes | 100 | 5.429 | 4.525 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Patch File | PASS |  | clean | yes | 100 | 55.102 | 26.33 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 72.595 | 27.43 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell Date | PASS |  | clean | yes | 100 | 18.258 | 17.157 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 16.155 | 13.698 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Patch File | PASS |  | clean | yes | 100 | 53.8 | 10.089 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Python File Simple | PASS |  | clean | yes | 100 | 6.931 | 7.081 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell Date | PASS |  | clean | yes | 100 | 7.181 | 9.387 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Shell PWD | PASS |  | clean | yes | 100 | 7.282 | 9.84 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Patch File | PASS |  | clean | yes | 100 | 121.359 | 9.036 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Python File Simple | PASS |  | clean | yes | 100 | 15.853 | 13.848 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell Date | PASS |  | clean | yes | 100 | 11.443 | 11.693 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Shell PWD | PASS |  | clean | yes | 100 | 12.194 | 5.778 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Patch File | PASS |  | clean | yes | 100 | 299.043 | 210.533 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 139.357 | 164.565 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell Date | PASS |  | clean | yes | 100 | 109.079 | 112.588 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 167.073 | 137.999 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Patch File | PASS |  | clean | yes | 100 | 44.826 | 7.584 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Simple | PASS |  | clean | yes | 100 | 4.826 | 4.626 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date | PASS |  | clean | yes | 100 | 3.523 | 4.325 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell PWD | PASS |  | clean | yes | 100 | 4.024 | 3.974 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Patch File | PASS |  | clean | yes | 100 | 33.546 | 24.625 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Python File Simple | PASS |  | clean | yes | 100 | 11.692 | 8.334 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell Date | PASS |  | clean | yes | 100 | 6.881 | 7.031 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Shell PWD | PASS |  | clean | yes | 100 | 10.74 | 6.93 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Patch File | FAIL |  | clean | yes | 0 | 53.044 | 12.041 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Simple | PASS |  | recovered | yes | 100 | 22.316 | 28.082 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell Date | PASS |  | recovered | yes | 100 | 19.661 | 18.91 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell PWD | PASS |  | recovered | yes | 100 | 21.366 | 24.021 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Patch File | FAIL |  | clean | yes | 0 | 52.741 | 13.997 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Simple | PASS |  | recovered | yes | 100 | 25.475 | 25.225 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell Date | PASS |  | recovered | yes | 100 | 24.725 | 25.126 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell PWD | PASS |  | recovered | yes | 100 | 34.801 | 31.889 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Patch File | FAIL |  | clean | maybe | 0 | 45.525 | 7.181 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Python File Simple | PASS |  | recovered | yes | 100 | 11.642 | 11.14 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell Date | PASS |  | recovered | yes | 100 | 9.537 | 9.438 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Shell PWD | PASS |  | recovered | yes | 100 | 9.335 | 8.787 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File | PASS |  | clean | yes | 100 | 55.5 | 59.169 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Simple | PASS |  | clean | yes | 100 | 15.704 | 15.452 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date | PASS |  | clean | yes | 100 | 10.59 | 17.159 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell PWD | PASS |  | clean | yes | 100 | 12.695 | 9.738 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File | PASS |  | clean | yes | 100 | 43.338 | 95.456 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Simple | PASS |  | clean | yes | 100 | 25.037 | 12.746 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date | PASS |  | clean | yes | 100 | 12.746 | 18.309 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell PWD | PASS |  | clean | yes | 100 | 14.351 | 12.195 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File | FAIL |  | clean | yes | 0 | 45.071 | 13.095 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Simple | TIMEOUT |  | clean | yes | 100 | 120.017 | 120.008 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date | PASS |  | recovered | yes | 100 | 33.044 | 31.841 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell PWD | TIMEOUT |  | recovered | yes | 100 | 120.01 | 120.008 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File | FAIL |  | clean | yes | 0 | 37.757 | 13.296 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Simple | PASS |  | recovered | yes | 100 | 54.095 | 53.643 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date | PASS |  | recovered | yes | 100 | 50.789 | 50.438 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell PWD | PASS |  | recovered | yes | 100 | 24.374 | 24.674 |
| opencode | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.003 | 120.004 |
| opencode | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 103.165 | 120.003 |
| opencode | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date | TIMEOUT |  | clean | no | 0 | 120.003 | 120.003 |
| opencode | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 120.005 | 120.005 |
| opencode | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File | TIMEOUT |  | clean | no | 0 | 120.003 | 120.004 |
| opencode | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 120.003 | 120.005 |
| opencode | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date | PASS |  | clean | yes | 100 | 120.003 | 82.323 |
| opencode | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell PWD | PASS |  | clean | yes | 100 | 86.028 | 109.536 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 65.624 | 38.813 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 13.248 | 12.595 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 14.801 | 13.096 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 20.365 | 13.298 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Save File | PASS |  | clean | yes | 100 | 13.751 | 16.105 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 13.697 | 13.798 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 13.849 | 12.696 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell File | PASS |  | clean | yes | 100 | 16.606 | 13.098 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Nonce Proof | PASS |  | clean | yes | 100 | 59.062 | 56.555 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 112.443 | 63.871 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 12.895 | 12.295 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 18.51 | 13.298 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted RU | FAIL | answered without invoking tool | clean | no | 0 | 17.507 | 16.406 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Save File | PASS |  | clean | yes | 100 | 18.41 | 14.952 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 14.801 | 11.694 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date RU | FAIL | answered without invoking tool | clean | no | 0 | 16.053 | 13.097 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell File | PASS |  | clean | yes | 100 | 18.356 | 13.697 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Nonce Proof | PASS |  | clean | yes | 100 | 51.993 | 57.106 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 45.976 | 13.997 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 108.331 | 108.578 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted DE | TIMEOUT |  | clean | yes | 100 | 120.008 | 120.015 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 44.224 | 43.772 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Save File | PASS |  | recovered | yes | 100 | 30.39 | 29.886 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date DE | TIMEOUT |  | clean | yes | 100 | 120.011 | 120.008 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 32.743 | 32.345 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell File | PASS |  | recovered | yes | 100 | 37.605 | 32.795 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Nonce Proof | PASS |  | recovered | yes | 100 | 95.349 | 117.555 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 42.369 | 14.701 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 58.106 | 57.808 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 48.134 | 47.831 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 62.626 | 62.368 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Save File | PASS |  | recovered | yes | 100 | 43.47 | 43.12 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 71.491 | 70.036 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 50.49 | 50.19 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell File | PASS |  | recovered | yes | 100 | 39.209 | 46.38 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Nonce Proof | TIMEOUT |  | recovered | yes | 100 | 120.008 | 120.01 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 39.854 | 7.33 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Weekly Plan Next Week | FAIL | answered without invoking tool | clean | no | 0 | 5.275 | 5.075 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Web Search JSON Ranked | FAIL | answered without invoking tool | clean | no | 0 | 99.187 | 36.447 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 29.228 | 88.604 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Web Search JSON Ranked | FAIL | answered without invoking tool | clean | no | 0 | 83.491 | 17.053 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 13.042 | 27.928 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Web Search JSON Ranked | FAIL | answered without invoking tool | clean | no | 0 | 211.724 | 162.071 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Weekly Plan Next Week | FAIL | answered without invoking tool | clean | no | 0 | 135.005 | 80.037 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 600.017 | 464.164 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 281.569 | 365.302 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 48.654 | 28.818 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 8.63 | 8.18 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 45.459 | 31.773 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Weekly Plan Next Week | FAIL | answered without invoking tool | clean | no | 0 | 17.246 | 31.724 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Web Search JSON Ranked | FAIL |  | recovered | yes | 0 | 119.189 | 93.134 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Weekly Plan Next Week | FAIL |  | clean | yes | 0 | 13.839 | 14.84 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Web Search JSON Ranked | TIMEOUT |  | clean | yes | 0 | 120.007 | 120.008 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Weekly Plan Next Week | NO_TOOL_CALL |  | clean | no | 0 | 88.176 | 86.725 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 62.63 | 51.11 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Weekly Plan Next Week | FAIL |  | recovered | yes | 0 | 120.008 | 19.349 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Web Search JSON Ranked | NO_TOOL_CALL |  | recovered | maybe | 0 | 102.407 | 74.504 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Weekly Plan Next Week | FAIL |  | recovered | yes | 0 | 120.008 | 96.946 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Web Search JSON Ranked | TIMEOUT |  | recovered | yes | 0 | 95.137 | 120.007 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Weekly Plan Next Week | FAIL |  | recovered | yes | 0 | 22.257 | 20.05 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Web Search JSON Ranked | TIMEOUT |  | recovered | yes | 0 | 120.009 | 120.008 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Weekly Plan Next Week | TIMEOUT |  | recovered | yes | 0 | 99.596 | 120.008 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | JSON Rank From File | FAIL | answered without invoking tool | clean | no | 0 | 35.892 | 6.829 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Web Fetch JSON Raw | FAIL | answered without invoking tool | clean | no | 0 | 5.776 | 5.827 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | markdown | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 8.333 | 8.332 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | JSON Rank From File | FAIL |  | clean | no | 0 | 90.714 | 298.514 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Web Fetch JSON Raw | PASS |  | clean | yes | 100 | 30.329 | 234.87 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | markdown | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 58.243 | 15.499 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 121.729 | 42.358 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Web Fetch JSON Raw | FAIL |  | clean | no | 0 | 56.086 | 33.535 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 167.121 | 255.264 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | JSON Rank From File | FAIL | answered without invoking tool | clean | no | 0 | 67.043 | 15.794 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Web Fetch JSON Raw | PASS |  | clean | yes | 100 | 18.599 | 13.792 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | markdown | Web Search JSON Ranked | FAIL | answered without invoking tool | clean | no | 0 | 28.667 | 38.038 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 378.397 | 136.914 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Web Fetch JSON Raw | FAIL | answered without invoking tool | clean | no | 0 | 254.873 | 74.879 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | markdown | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 153.801 | 232.918 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 340.96 | 298.918 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Web Fetch JSON Raw | TIMEOUT |  | clean | no | 0 | 513.633 | 600.026 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 600.018 | 533.619 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | JSON Rank From File | FAIL |  | clean | no | 0 | 47.817 | 39.7 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Fetch JSON Raw | PASS |  | clean | yes | 100 | 9.333 | 10.988 |
| continue-cli | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 8.232 | 16.049 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | JSON Rank From File | PASS |  | clean | yes | 100 | 21.61 | 18.455 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Web Fetch JSON Raw | FAIL | answered without invoking tool | clean | no | 0 | 32.334 | 21.411 |
| continue-cli | local/nemotron-3-nano:4b | ollama | 6cc467f054393a55e98a74098abde0c762ffb6d1d8cd64becf30458f38886197 | tool | Web Search JSON Ranked | FAIL |  | clean | no | 0 | 22.92 | 22.564 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | JSON Rank From File | FAIL |  | recovered | yes | 0 | 113.105 | 74.268 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 34.887 | 38.797 |
| gptme | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Web Search JSON Ranked | FAIL |  | recovered | yes | 0 | 68.161 | 47.766 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | JSON Rank From File | TIMEOUT |  | clean | no | 0 | 120.016 | 120.008 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Web Fetch JSON Raw | TIMEOUT |  | recovered | yes | 100 | 105.291 | 120.008 |
| gptme | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Web Search JSON Ranked | TIMEOUT |  | clean | yes | 0 | 120.008 | 120.009 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | JSON Rank From File | PASS |  | clean | yes | 100 | 55.635 | 17.952 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 15.098 | 14.898 |
| gptme | local/ministral-3:8b | ollama | 1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71 | tool | Web Search JSON Ranked | FAIL |  | clean | yes | 0 | 99.381 | 16.749 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | JSON Rank From File | NO_TOOL_CALL |  | clean | no | 0 | 81.439 | 42.103 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 40.951 | 37.897 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Web Search JSON Ranked | NO_TOOL_CALL |  | recovered | maybe | 0 | 120.008 | 49.921 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | JSON Rank From File | TIMEOUT |  | clean | yes | 0 | 75.322 | 120.012 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Web Fetch JSON Raw | FAIL |  | recovered | yes | 0 | 19.505 | 17.701 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Web Search JSON Ranked | TIMEOUT |  | clean | yes | 0 | 37.693 | 120.017 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | JSON Rank From File | TIMEOUT |  | recovered | yes | 0 | 120.009 | 120.008 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 120.009 | 57.836 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Web Search JSON Ranked | TIMEOUT |  | recovered | yes | 0 | 72.216 | 120.019 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | JSON Rank From File | PASS |  | recovered | yes | 100 | 120.008 | 76.234 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 89.005 | 87.25 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Search JSON Ranked | PASS |  | recovered | yes | 100 | 120.008 | 112.005 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | JSON Rank From File | PASS |  | recovered | yes | 100 | 114.409 | 85.184 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 83.283 | 85.223 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Search JSON Ranked | TIMEOUT |  | recovered | yes | 100 | 120.007 | 120.008 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 69.565 | 29.928 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Fetch JSON Raw | PASS |  | clean | yes | 100 | 32.437 | 26.475 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 74.071 | 50.424 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 66.664 | 17.361 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 18.506 | 12.041 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 9.134 | 11.241 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 9.385 | 11.69 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 9.987 | 11.491 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Save File | PASS |  | clean | yes | 100 | 9.135 | 15.098 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 9.237 | 10.59 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 8.784 | 9.388 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell File | PASS |  | clean | yes | 100 | 9.236 | 8.734 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Fetch JSON Raw | FAIL |  | clean | no | 0 | 33.49 | 38.601 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Nonce Proof | PASS |  | clean | yes | 100 | 48.374 | 31.334 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 191.245 | 63.66 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 18.256 | 18.507 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 36.443 | 26.172 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 21.261 | 49.271 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 8.732 | 8.632 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 9.085 | 10.486 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 11.288 | 13.193 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Save File | PASS |  | clean | yes | 100 | 9.836 | 11.339 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 10.687 | 9.835 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 8.783 | 10.487 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell File | PASS |  | clean | yes | 100 | 8.282 | 10.637 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Fetch JSON Raw | FAIL |  | clean | no | 0 | 600.015 | 42.357 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Nonce Proof | PASS |  | clean | yes | 100 | 29.228 | 28.277 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 88.909 | 50.774 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 23.269 | 79.337 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | JSON Rank From File | PASS |  | clean | yes | 100 | 21.911 | 23.465 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File From Prepared Patch | FAIL |  | clean | no | 0 | 20.811 | 10.991 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 11.389 | 10.287 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 9.585 | 11.389 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 11.388 | 11.489 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Save File | PASS |  | clean | yes | 100 | 9.285 | 10.137 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 10.487 | 10.137 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 9.385 | 8.834 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell File | PASS |  | clean | yes | 100 | 8.533 | 10.587 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Fetch JSON Raw | PASS |  | clean | yes | 100 | 43.01 | 38.399 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Nonce Proof | PASS |  | clean | yes | 100 | 27.673 | 29.678 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Search JSON Ranked | FAIL | answered without invoking tool | clean | no | 0 | 74.725 | 71.671 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 36.14 | 22.162 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | JSON Rank From File | PASS |  | clean | yes | 100 | 31.931 | 24.867 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 18.052 | 37.595 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 9.486 | 14.397 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 11.639 | 12.743 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 10.086 | 13.794 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Save File | PASS |  | clean | yes | 100 | 9.184 | 25.019 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 9.033 | 9.685 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 10.589 | 12.291 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell File | PASS |  | clean | yes | 100 | 9.284 | 8.833 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Fetch JSON Raw | FAIL | answered without invoking tool | clean | no | 0 | 23.618 | 33.386 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Nonce Proof | PASS |  | clean | yes | 100 | 35.995 | 33.537 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 117.823 | 55.939 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 31.133 | 19.908 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | JSON Rank From File | PASS |  | clean | yes | 100 | 155.413 | 66.576 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 30.932 | 44.825 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Python File Quoted | PASS |  | clean | yes | 100 | 18.004 | 14.506 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Python File Quoted DE | PASS |  | clean | yes | 100 | 17.204 | 15.7 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Python File Quoted RU | PASS |  | clean | yes | 100 | 14.65 | 20.16 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Save File | PASS |  | clean | yes | 100 | 12.746 | 21.864 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Shell Date DE | PASS |  | clean | yes | 100 | 13.194 | 15.049 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Shell Date RU | PASS |  | clean | yes | 100 | 12.291 | 12.191 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Shell File | PASS |  | clean | yes | 100 | 22.314 | 12.392 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Web Fetch JSON Raw | FAIL |  | clean | no | 0 | 67.722 | 58.25 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Web Nonce Proof | PASS |  | clean | yes | 100 | 91.868 | 68.968 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 89.718 | 68.069 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Weekly Plan Next Week | FAIL | answered without invoking tool | clean | no | 0 | 49.276 | 39.704 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Patch File | FAIL | answered without invoking tool | clean | no | 0 | 56.687 | 26.973 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 16.449 | 14.144 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Shell Date | PASS |  | clean | yes | 100 | 11.338 | 10.888 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 12.142 | 11.139 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Patch File | PASS |  | clean | yes | 100 | 74.928 | 19.055 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 13.997 | 15.503 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell Date | PASS |  | clean | yes | 100 | 11.589 | 10.888 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 11.139 | 11.79 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File | PASS |  | clean | yes | 100 | 17.953 | 39.349 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Simple | PASS |  | clean | yes | 100 | 13.393 | 20.809 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date | PASS |  | clean | yes | 100 | 13.142 | 10.238 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell PWD | PASS |  | clean | yes | 100 | 13.746 | 11.94 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File | PASS |  | clean | yes | 100 | 19.91 | 15.797 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Simple | PASS |  | clean | yes | 100 | 14.296 | 16.198 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date | PASS |  | clean | yes | 100 | 14.847 | 12.342 |
| continue-cli | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell PWD | PASS |  | clean | yes | 100 | 12.14 | 11.89 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | JSON Rank From File | PASS |  | clean | yes | 100 | 89.756 | 202.553 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File From Prepared Patch | PASS |  | clean | yes | 100 | 57.4 | 42.005 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted | PASS |  | clean | yes | 100 | 12.24 | 19.357 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted DE | PASS |  | clean | yes | 100 | 17.301 | 14.996 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted RU | PASS |  | clean | yes | 100 | 11.388 | 13.193 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Save File | PASS |  | clean | yes | 100 | 16.052 | 24.419 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date DE | PASS |  | clean | yes | 100 | 13.692 | 12.992 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date RU | PASS |  | clean | yes | 100 | 12.289 | 11.989 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell File | PASS |  | clean | yes | 100 | 11.288 | 11.689 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Fetch JSON Raw | FAIL |  | clean | no | 0 | 134.056 | 216.977 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Nonce Proof | FAIL |  | clean | no | 0 | 49.671 | 50.973 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Search JSON Ranked | PASS |  | clean | yes | 100 | 137.758 | 117.111 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Weekly Plan Next Week | PASS |  | clean | yes | 100 | 49.619 | 52.58 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | JSON Rank From File | PASS |  | recovered | yes | 100 | 106.345 | 74.476 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 14.844 | 14.344 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 106.5 | 108.156 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted DE | TIMEOUT |  | recovered | yes | 100 | 120.016 | 120.008 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 43.956 | 43.303 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Save File | PASS |  | recovered | yes | 100 | 31.381 | 30.632 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date DE | TIMEOUT |  | recovered | yes | 100 | 120.008 | 120.009 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 36.491 | 34.542 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell File | PASS |  | recovered | yes | 100 | 40.899 | 42.406 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 89.908 | 66.706 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Nonce Proof | PASS |  | recovered | yes | 100 | 87.948 | 87.754 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Web Search JSON Ranked | PASS |  | recovered | yes | 100 | 120.008 | 108.796 |
| gptme | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Weekly Plan Next Week | PASS |  | recovered | yes | 100 | 56.684 | 56.132 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | JSON Rank From File | PASS |  | recovered | yes | 100 | 114.411 | 85.897 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Patch File From Prepared Patch | FAIL |  | clean | yes | 0 | 15.097 | 14.545 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted | PASS |  | recovered | yes | 100 | 58.94 | 58.437 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted DE | PASS |  | recovered | yes | 100 | 47.615 | 48.926 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Python File Quoted RU | PASS |  | recovered | yes | 100 | 62.448 | 62.555 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Save File | PASS |  | recovered | yes | 100 | 43.257 | 42.814 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date DE | PASS |  | recovered | yes | 100 | 74.125 | 73.078 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell Date RU | PASS |  | recovered | yes | 100 | 50.471 | 50.626 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Shell File | PASS |  | recovered | yes | 100 | 46.968 | 46.064 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Fetch JSON Raw | PASS |  | recovered | yes | 100 | 93.966 | 70.115 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Nonce Proof | TIMEOUT |  | recovered | yes | 100 | 113.604 | 120.008 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Web Search JSON Ranked | TIMEOUT |  | recovered | yes | 100 | 120.008 | 120.009 |
| gptme | local/aravhawk/qwen3.5-opus-4.6-text:9b | ollama | 74348a6ec8d24b1098799494443e2455f8f77e630c6de078429d731b2647df65 | tool | Weekly Plan Next Week | PASS |  | recovered | yes | 100 | 107.595 | 113.606 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | markdown | Patch File | TIMEOUT |  | clean | no | 0 | 600.023 | 600.022 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 379.013 | 199.964 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | markdown | Shell Date | PASS |  | clean | yes | 100 | 202.167 | 177.253 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 170.846 | 258.692 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Patch File | PASS |  | clean | yes | 100 | 56.942 | 41.01 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Python File Simple | PASS |  | clean | yes | 100 | 22.771 | 15.55 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell Date | PASS |  | clean | yes | 100 | 12.541 | 16.655 |
| continue-cli | local/qwen3.5:9b | ollama | 6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7 | tool | Shell PWD | PASS |  | clean | yes | 100 | 12.142 | 12.744 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | markdown | Patch File | PASS |  | clean | yes | 100 | 107.56 | 42.106 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 19.557 | 14.649 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | markdown | Shell Date | PASS |  | clean | yes | 100 | 14.648 | 12.442 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 11.09 | 11.942 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | markdown | Patch File | TIMEOUT |  | clean | no | 0 | 600.017 | 600.027 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | markdown | Python File Simple | TIMEOUT |  | clean | no | 0 | 600.025 | 600.018 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | markdown | Shell Date | TIMEOUT |  | clean | no | 0 | 600.034 | 600.015 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | markdown | Shell PWD | TIMEOUT |  | clean | no | 0 | 600.017 | 600.015 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | markdown | Patch File | FAIL |  | clean | no | 0 | 121.527 | 16.351 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | markdown | Python File Simple | PASS |  | clean | yes | 100 | 7.079 | 8.282 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | markdown | Shell Date | PASS |  | clean | yes | 100 | 6.428 | 7.18 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | markdown | Shell PWD | PASS |  | clean | yes | 100 | 6.629 | 6.979 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File | NO_TOOL_CALL |  | clean | maybe | 0 | 120.008 | 69.613 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Simple | FAIL |  | recovered | yes | 0 | 47.121 | 47.768 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date | PASS |  | recovered | yes | 100 | 47.868 | 48.822 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Patch File | NO_TOOL_CALL |  | clean | maybe | 0 | 79.736 | 67.359 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Python File Simple | FAIL |  | recovered | yes | 0 | 46.167 | 46.817 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell Date | PASS |  | recovered | yes | 100 | 47.466 | 47.419 |
| gptme | local/mistral-nemo:12b | ollama | e7e06d107c6c86ed0cf45445f1790720b5092149c4c95f4d965844e9afbfdc89 | tool | Shell PWD | PASS |  | recovered | yes | 100 | 42.956 | 43.458 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Patch File | PASS |  | recovered | yes | 100 | 45.562 | 12.891 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Simple | PASS |  | recovered | yes | 100 | 11.69 | 14.046 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date | PASS |  | recovered | yes | 100 | 14.194 | 14.646 |
| gptme | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell PWD | PASS |  | recovered | yes | 100 | 9.483 | 9.989 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Patch File | PASS |  | recovered | yes | 100 | 119.123 | 59.891 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Simple | PASS |  | recovered | yes | 100 | 43.454 | 40.101 |
| gptme | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date | PASS |  | recovered | yes | 100 | 64.352 | 50.12 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Patch File | FAIL | answered without invoking tool | clean | no | 0 | 33.087 | 4.724 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Python File Simple | PASS |  | clean | yes | 100 | 5.927 | 5.226 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell Date | PASS |  | clean | yes | 100 | 5.075 | 5.275 |
| continue-cli | local/qwen2.5:7b | ollama | 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | tool | Shell PWD | PASS |  | clean | yes | 100 | 4.975 | 5.126 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Patch File | PASS |  | clean | yes | 100 | 89.76 | 26.824 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Python File Simple | PASS |  | clean | yes | 100 | 48.32 | 34.738 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell Date | PASS |  | clean | yes | 100 | 21.66 | 14.346 |
| continue-cli | local/qwen3:8b | ollama | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 | tool | Shell PWD | PASS |  | clean | yes | 100 | 34.237 | 39.199 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | tool | Patch File | TIMEOUT |  | clean | no | 0 | 600.028 | 600.023 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 600.017 | 600.016 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | tool | Shell Date | PASS |  | clean | yes | 100 | 226.315 | 355.742 |
| continue-cli | local/qwen3:14b | ollama | bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8 | tool | Shell PWD | PASS |  | clean | yes | 100 | 239.496 | 186.18 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | tool | Patch File | PASS |  | clean | yes | 100 | 50.526 | 54.034 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | tool | Python File Simple | PASS |  | clean | yes | 100 | 12.791 | 18.855 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | tool | Shell Date | PASS |  | clean | yes | 100 | 16.007 | 11.596 |
| continue-cli | local/fredrezones55/qwen3.5-opus:9b | ollama | 8d160636f9cbca81667d7c5582952bfc471b66891ac623c751fd3b0a9ced3f59 | tool | Shell PWD | PASS |  | clean | yes | 100 | 11.09 | 15.098 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | tool | Patch File | TIMEOUT |  | clean | no | 0 | 600.023 | 600.015 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | tool | Python File Simple | TIMEOUT |  | clean | no | 0 | 600.015 | 600.015 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | tool | Shell Date | TIMEOUT |  | clean | no | 0 | 600.015 | 600.014 |
| continue-cli | local/fredrezones55/qwen3.5-opus:27b | ollama | 914789b72c24baadc39a9f14a49b8ed5364d62e44635936ed19932beb7b4261d | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 600.044 | 600.017 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | tool | Patch File | FAIL |  | clean | no | 0 | 79.74 | 13.393 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | tool | Python File Simple | PASS |  | clean | yes | 100 | 7.832 | 7.53 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | tool | Shell Date | PASS |  | clean | yes | 100 | 6.779 | 7.931 |
| continue-cli | local/cryptidbleh/gemma4-claude-opus-4.6:latest | ollama | 0961fd31e5ae57fe3f7bba84ec4dbda92fbd90c1151b31e002864a423e297cf4 | tool | Shell PWD | PASS |  | clean | yes | 100 | 7.18 | 7.531 |
| continue-cli | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Patch File | PASS |  | clean | yes | 100 | 23.423 | 5.377 |
| continue-cli | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Python File Simple | FAIL | answered without invoking tool | clean | no | 0 | 4.674 | 4.875 |
| continue-cli | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Shell Date | PASS |  | clean | yes | 100 | 4.225 | 4.375 |
| continue-cli | local/granite4:3b | ollama | 89962fcc75239ac434cdebceb6b7e0669397f92eaef9c487774b718bc36a3e5f | tool | Shell PWD | PASS |  | clean | yes | 100 | 4.373 | 4.824 |
| continue-cli | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.57 | 2.62 |
| continue-cli | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.67 | 2.47 |
| continue-cli | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.77 | 2.771 |
| continue-cli | local/phi3.5:latest | ollama | 61819fb370a3c1a9be6694869331e5f85f867a079e9271d66cb223acb81d04ba | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.52 | 2.971 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Patch File | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.02 | 3.374 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Python File Simple | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.221 | 3.021 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell Date | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 2.97 | 3.522 |
| continue-cli | local/gemma3:12b | ollama | f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a | tool | Shell PWD | TOOL_UNSUPPORTED | tool unsupported by backend | clean | no | 0 | 3.222 | 2.771 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Patch File | PASS |  | clean | yes | 100 | 58.849 | 10.638 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Python File Simple | PASS |  | clean | yes | 100 | 8.032 | 8.634 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell Date | PASS |  | clean | yes | 100 | 6.782 | 6.73 |
| continue-cli | local/gemma4:e2b | ollama | 7fbdbf8f5e45a75bb122155ed546e765b4d9c53a1285f62fd9f506baa1c5a47e | tool | Shell PWD | PASS |  | clean | yes | 100 | 8.884 | 7.932 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Patch File | PASS |  | clean | yes | 100 | 137.969 | 38.599 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Python File Simple | PASS |  | clean | yes | 100 | 34.542 | 15.7 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell Date | PASS |  | clean | yes | 100 | 11.941 | 10.639 |
| continue-cli | local/gemma4:e4b | ollama | c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb | tool | Shell PWD | PASS |  | clean | yes | 100 | 26.272 | 12.893 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Patch File | PASS |  | clean | yes | 100 | 376.899 | 292.813 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Python File Simple | PASS |  | clean | yes | 100 | 168.089 | 144.183 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell Date | PASS |  | clean | yes | 100 | 120.539 | 124.54 |
| continue-cli | local/gpt-oss:20b | ollama | 17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7 | tool | Shell PWD | TIMEOUT |  | clean | no | 0 | 377.754 | 600.032 |
| continue-cli | local/mistral-small:24b | ollama | 8039dd90c1138d772437a0779a33b7349efd5d9cca71edcd26e4dd463f90439d | tool | Patch File | TIMEOUT |  | clean | no | 0 | 600.016 | 600.016 |

generated at 2026-05-02 09:54:23 UTC | git commit e074805
