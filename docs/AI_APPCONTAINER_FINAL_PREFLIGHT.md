# Atualização · 2.3D3A.4-BRIDGE

As lacunas técnicas de bridge, coletores e pinning foram implementadas nesta fase; a classificação final e os limites atuais estão em [Native bridge](AI_APPCONTAINER_NATIVE_BRIDGE.md) e [OS receipts](AI_APPCONTAINER_OS_RECEIPTS.md). O PREFLIGHT_PARTIAL abaixo é histórico. NativeProfileBridge implementa o port com NativeProfileCalls preparada e API ausente por padrão; nenhum runner o instancia/conecta. Create/Delete reais permanecem NOT_AUTHORIZED. Processo/Job/handles/diretórios foram observados no Windows com Child/Jobs benignos; ownership/Delete reais permanecem NONE/NOT_VERIFIED. Journal usa handles, SD por handle, caminhos finais e File IDs/volume, com mitigação e falha fechada nas divergências, sem garantia universal contra TOCTOU ou escritor do mesmo usuário/SYSTEM. Raiz persistente LOCALAPPDATA não criada. ISOLATED_RESEARCH indisponível, FS/rede não comprovados. Resultados desta fase em [VERIFICATION](VERIFICATION.md).

# Final preflight · 2.3D3A.4-GATE

**PREFLIGHT_PARTIAL — NOT_AUTHORIZED.** Preparação revisável, sem ensaio real. Este registro substitui a interpretação de prontidão da fase anterior; preserva seus resultados como histórico. `ISOLATED_RESEARCH_UNAVAILABLE`, `DEVELOPMENT_MOCK=NOT_SANDBOXED`, filesystem/network `NOT_VERIFIED`.

Baseline conferido: `main`, HEAD `ffeaf0674a67d3114cffe9b85cc177a27259564c`, working tree limpa, nenhuma diferença para a referência. Commit local desta entrega: `fix: harden appcontainer native execution preflight`; HEAD final deve ser consultado no Git e na resposta da entrega, pois um commit não contém seu próprio hash.

## Quatro bloqueadores

| Item | Preparação entregue | Limite e estado |
| --- | --- | --- |
| A · adapter | `ProfileOperationPort` tipado explicita a fronteira futura; contrato sintético exige SID com gramática estrita, nome fixo, capabilities vazias, HRESULT S_OK, confirmação externa e FreeSid. Bindings e memória revisados. | **DEFERRED**: não existe implementação nativa do port nem ligação ao runner. Código arbitrário do usuário com ctypes não está coberto pelo bloqueio das entradas do projeto. |
| B · journal | `WindowsJournalSecurity`, owner atual, volume fixo local, DACL protegida exata proprietário/SYSTEM, read-back em diretórios/arquivos/temporários, rejeição de reparse/junction/hardlink e identidade do arquivo. | **TESTED** em fixtures Win32; **NOT_VERIFIED** contra worker AppContainer. Raiz persistente proposta não criada nem certificada. Corridas contra escritor malicioso do supervisor não estão resolvidas. |
| C · remoção | Verificador independente somente leitura correlaciona journal, identidade, storage da API e mapeamento exato com observações de recursos. `CLEANED` agora exige resultado correspondente e positivo. | **IMPLEMENTED / TESTED_MOCK**. Consultas exatas nativas executadas sem Delete. Coleta operacional nativa de recibos de processo/Job/handles/diretórios continua **DEFERRED**; rollback real **PREPARED_NOT_EXECUTED**. |
| D · crash | Intenção durável antes de Create; nenhuma limpeza após falha de persistência, retorno perdido ou SID conflitante. Journal falho bloqueia reutilização. Recuperação só leitura. | **TESTED_MOCK**: crash antes/durante/depois de Create, fsync/replace/read-back, divergência, presença/ausência e resposta de Delete perdida. Crash real/power loss não testado. |

O gate não pode ser `PREFLIGHT_READY_FOR_HUMAN_REVIEW`: falta completar e revisar o bridge e os coletores operacionais sem conectá-los, além de aceitar os limites de caminho/ACL. Nenhum status, JSON, variável, mock ou parâmetro concede autorização. `execute_authorized_test`, `create_profile` e `delete_profile` continuam levantando `REQUIRES_APPROVAL`; nenhuma CLI de mutação foi adicionada.

## Revisão Win32

As quatro funções ficam em userenv.dll e retornam HRESULT de 32 bits (`c_long` no Windows). Create recebe três LPCWSTR, `POINTER(SID_AND_ATTRIBUTES)` e DWORD; saída `PSID*` inicializada em NULL. Somente S_OK e SID não NULL permitem continuar no seam sintético. ERROR_ALREADY_EXISTS usa normalização `hr & 0xffffffff`; S_FALSE e demais códigos abortam. SID retornado/derivado usa FreeSid; string do getter usa CoTaskMemFree em ole32. Falhas de conversão também liberam memória. Derive agora testa NULL e tem liberação em finally inclusive no erro parcial. Getter S_OK/NULL é erro; erro de acesso ao storage não vira ausência por `Path.exists()`.

Chamadas Create/Delete do contrato foram exercitadas **somente com FakeUserenv**, nunca com Windows real. Derive, getter, registro KEY_READ, leitura de descritores e controles Job existentes foram exercitados no Windows. Ausência observada: pasta e mapeamento do perfil reservado ausentes. Isso não prova ownership. A documentação de Delete também diz que excluir perfil inexistente pode retornar sucesso e que handles abertos impedem remoção completa; por isso o verificador é independente. Não se adotou retry automático sugerido pela API quando ownership é incerto.

Referências consultadas nesta fase: [Create](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile), [Delete](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile), [Derive](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deriveappcontainersidfromappcontainername), [getter](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-getappcontainerfolderpath), [GetFileSecurityW](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-getfilesecurityw), [controle do descritor](https://learn.microsoft.com/en-us/windows/win32/secauthz/security-descriptor-control), [atributos de arquivo](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesw).

## Journal

O local futuro continua `%LOCALAPPDATA%/Escryptorio/IsolationPoC/journals`. Nenhum diretório persistente foi criado. Fixtures descartáveis recebem DACL `D:P` com apenas duas ACEs explícitas de full access herdáveis, SYSTEM e SID do supervisor. A checagem lê OWNER+DACL por GetFileSecurityW, owner/control por GetSecurityDescriptorOwner/GetSecurityDescriptorControl e ACEs com GetSecurityDescriptorDacl. Recusa owner divergente/defaulted, DACL não protegida, NULL, ACE ampla/extra/herdada/de tipo inesperado ou direitos diferentes. Nenhuma ACE concede direitos a pacote, capacidades ou usuários amplos. Isto é análise estática da política, **não AccessCheck nem prova de negação ao worker**.

Raiz precisa ser absoluta, sem UNC, ADS ou `..`, volume DRIVE_FIXED, resolve idêntico e sem FILE_ATTRIBUTE_REPARSE_POINT em qualquer ancestral. Verifica novamente cada caminho antes de leitura/publicação. Um filho só pode receber proteção se novo e vazio dentro da raiz controlada. Temporário herda a DACL restrita e recebe proteção explícita antes de escrever conteúdo. Diretório da operação e manifesto têm proteção própria. Arquivos com múltiplos links e troca de identidade do journal são recusados.

Schema Record v1, hash domain-separated, IDs, token, SIDs, geração, flush/fsync/replace/read-back foram preservados. Diretório da operação e manifesto têm criação exclusiva; não reabrem sessões antigas. Troca byte a byte, geração diferente, registro antigo ou corrupção envenenam o writer. `validate_journal_preflight` rejeita journal legado sem guard: `JOURNAL_SECURITY_NOT_VERIFIED`. O mock legado pode continuar sem ACL, identificado somente como TESTED_MOCK. A futura ponte deverá exigir essa validação antes de Create e nas etapas relevantes; ela ainda não existe.

SHA-256 é integridade acidental, não autenticação. Paths não ficam presos por handles durante toda a operação; proprietário/SYSTEM podem substituir recursos entre checagens. Não há garantia contra atacante com escrita legítima, administrador, falha de energia ou redirecionamento concorrente. Por esses limites, esta entrega não certifica um local operacional seguro.

## Recuperação e remoção

Consulte [verificação de rollback](AI_APPCONTAINER_ROLLBACK_VERIFICATION.md). Journal falho após Create mantém recurso e estado volátil de revisão manual; o arquivo pode estar em CREATING ou conter publicação ainda não confirmada. Nenhum desses estados aciona Delete. Resposta perdida, SID divergente ou exclusão ambígua exigem `MANUAL_REVIEW_REQUIRED`. Mesmo um CLEANED v1 lido após reinício exige nova verificação de storage; o schema antigo não foi reinterpretado como prova nova. Não existe recuperação com exclusão automática, limpeza por prefixo ou enumeração geral.

## Relatório de entrega — 22 itens

| # | Resultado |
| --- | --- |
| 1 | HEAD inicial completo acima; final no Git/resposta, commit local com assunto exato. |
| 2 | Novos journal_security.py, rollback_verification.py, test_appcontainer_preflight.py e dois documentos de preflight/rollback. Alterados runner, journal, lifecycle, adapter, bindings, fixtures e documentos exigidos; lista exata no commit. |
| 3 | Revisão Win32 descrita acima, referências oficiais e HRESULT/memória cobertos. |
| 4 | Bridge operacional **DEFERRED**, fisicamente sem implementação/conexão ao runner disponível. |
| 5 | Zero chamadas reais Create/DeleteAppContainerProfile. |
| 6 | ACL e owner conferidos em fixtures Win32; negação por identidade AppContainer **NOT_VERIFIED**. |
| 7 | Reparse/junction/ancestrais recusados; junction real descartável testada sem seguir/excluir target. |
| 8 | Verificador read-only implementado; ausência limitada aos locais conhecidos. Recibos nativos ainda ausentes. |
| 9 | Estados preservados, sem reabertura automática, terminais bloqueiam reutilização. |
| 10 | Create/resposta/SID perdido conserva perfil sintético e exige revisão humana. |
| 11 | Matriz de falhas sintéticas em test_appcontainer_preflight.py e testes anteriores. |
| 12 | Suíte Python: resultados reais em [VERIFICATION](VERIFICATION.md). |
| 13 | Direcionados incluem seis arquivos; resultados reais em VERIFICATION. |
| 14 | Fingerprint financeiro esperado e resultado em VERIFICATION. |
| 15 | Replays somente em backup temporário, origem ro/query_only; resultados em VERIFICATION. |
| 16 | Nenhuma alteração em motor, ledger, estratégias, wallets, fills, migrations ou flags financeiras. |
| 17 | Token primário limitado, não elevado confirmado. Somente ACLs de fixtures, processos/Jobs benignos e listener efêmero nos testes existentes. Zero mudança global/registro/firewall/contas/serviços. |
| 18 | Nenhum perfil, journal operacional ou recurso global persistente criado; fixtures/journals sintéticos apenas em TEMP. Pytest pode reter diretórios recentes conforme sua política; não se declara que todo TEMP foi apagado. Arquivos do projeto e commit são a entrega. |
| 19 | Nenhum perfil, recurso desconhecido ou arquivo pessoal removido; somente recursos temporários próprios. |
| 20 | Riscos: corrida do mesmo usuário, receipts nativos ausentes, crash/power loss, compatibilidade runtime, FS/rede, CPU/disco não comprovados. |
| 21 | **PREFLIGHT_PARTIAL**, execução **NOT_AUTHORIZED**, isolamento indisponível. |
| 22 | Próxima decisão humana: revisar este commit e definir nova tarefa de preparação do bridge/coletores. Qualquer conexão e ensaio real exige commit revisado, autorização específica, perfil/política/rollback exatos e tarefa separada. Não iniciar D3B. |

Skills locais aplicadas: continuidade, segurança, revisão de código e segurança paper. Nenhuma ferramenta/dependência instalada, push ou PR realizado.
