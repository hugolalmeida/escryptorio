# PoC Windows · 2.3D3A.1

O resultado é PARTIAL_POC. Recursos e processos têm provas sintéticas específicas de enforcement. Filesystem e rede permanecem NOT_VERIFIED. ISOLATED_RESEARCH continua indisponível, e DEVELOPMENT_MOCK conserva seu contrato anterior.

## Estágios e hipóteses

| Estágio | Hipótese e teste mínimo | Resultado e decisão |
| --- | --- | --- |
| A | APIs de token/Job podem ser usadas por processo x64 sem elevação | Token primário limitado e APIs verificadas. Discovery somente leitura de configuração e objetos efêmeros |
| B | Suspender, associar ao Job e conferir limites antes do resume permite limitar fixtures | Alocação nativa e descendente recusados sob os limites, controles positivos aprovados. Timeout e término de árvore testados |
| C | Identidade restrita pode executar Python e negar canários/rede | Restricted Token falhou na inicialização do runtime. AppContainer sem perfil falhou na criação. DACL configurada apenas em fixtures, negação NOT_VERIFIED |
| D | Falhas parciais liberam processos/handles/diretórios e fluxo de contexto continua verificável | Injeções de falha, interrupção, morte do supervisor e integração sintética com gateway exercitadas |
| E | Fingerprint, replays e regressões podem ser preservados | Resultados atuais em [AI_ISOLATION_TEST_RESULTS.md](AI_ISOLATION_TEST_RESULTS.md) |

## Componentes e contrato

`windows_native.py` contém as assinaturas e estruturas Win32. `isolation_poc.py` possui política imutável, launcher, ownership, supervisor, árvore temporária e evidência estruturada. `isolation_probe.py` contém exclusivamente operações benignas fixas. O script mock anterior é copiado para a árvore temporária na integração offline.

IsolationPolicy v1 é uma dataclass congelada com validação estrita. Campos desconhecidos falham no construtor. Seus campos são schema_version, launcher_version, process_memory_bytes, job_memory_bytes, active_processes, timeout_ms, max_input_bytes, max_output_bytes e identity. launcher_version é windows-isolation-poc/1. identity admite APPCONTAINER, RESTRICTED_TOKEN e JOB_ONLY. O default solicita APPCONTAINER. JOB_ONLY exige seleção explícita para os controles de recursos.

O content_hash da política usa o domínio `escryptorio:isolation-policy:v1`, byte NUL e JSON canônico existente. Os campos da política entram no hash. SIDs aleatórios, diretórios temporários, tempos e PIDs operacionais ficam fora dessa identidade. A política pertence ao supervisor. O worker recebe somente entrada limitada e um nome de probe fixo, sem executável, código ou política fornecidos por bundle.

Padrões são 64 MiB por processo, 96 MiB por Job, um processo ativo, três segundos e 65.536 bytes para entrada e cada stream de saída. Tetos da PoC são 256 MiB, dois processos e dez segundos. A política de filesystem é DACL sintética e a política de rede solicitada por APPCONTAINER usa zero capabilities. A validação efetiva dessas fronteiras fica na evidência externa.

## Lançamento e recursos

O launcher usa CreateProcessW ou CreateProcessAsUserW com executável absoluto conhecido, command line construída por list2cmdline, CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT e EXTENDED_STARTUPINFO_PRESENT. A lista de handles herdáveis contém somente stdin/stdout/stderr. O Job é anônimo, sem handle herdado, com KILL_ON_JOB_CLOSE, PROCESS_MEMORY, JOB_MEMORY e ACTIVE_PROCESS. Os limites são lidos de volta e comparados antes de criar o processo. A associação e IsProcessInJob são conferidos antes de ResumeThread.

O runtime é copiado do Python instalado para worker/, com DLLs e stdlib, excluindo site-packages e módulos do projeto. O interpretador GUI pythonw.exe mantém seu nome original e recebe pipes explícitos. Um ensaio inicial com python.exe criou conhost.exe no Job. O interpretador GUI eliminou esse processo adicional e permitiu medir os limites com uma e duas fixtures Python. Não foram instalados pacotes ou alteradas permissões da instalação do Python.

O ambiente do filho contém somente SystemRoot, SystemDrive, TEMP, TMP e as duas flags de segurança fixadas em false. O diretório de trabalho fica na árvore sintética. Leitores e escritor concorrentes evitam bloqueio do supervisor. stdout/stderr possuem contadores independentes e armazenamento limitado. Timeout, cancelamento ou excesso terminam o Job e aguardam os processos. O orçamento de tokens anterior permanece SIMULATED.

Os limites de memória referem-se a commit. O teste usa VirtualAlloc/VirtualFree para uma solicitação fixa de 96 MiB sem tocar as páginas. A recusa nativa é comparada a uma política que permite a mesma solicitação e à consulta dos limites de Job. Pico contábil, RSS, memória física e commit negado possuem semânticas diferentes. Uma amostra de JobMemoryLimit isolado reportou pico acima do teto durante a tentativa recusada. O relatório não oferece uma garantia universal de teto instantâneo de RSS.

Os campos e os limites de memória de processo e de Job são documentados pela Microsoft. KILL_ON_JOB_CLOSE depende do fechamento do último handle do Job, por isso esse handle fica fora da lista herdável. [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [JOBOBJECT_EXTENDED_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

## Filesystem e rede

PocEnvironment cria protected/, allowed/, worker/ e outputs/ dentro de um TemporaryDirectory exclusivo. Há três arquivos canário e um SQLite sintético válido em protected/. O contexto autorizado em allowed/ é sintético. A DACL protegida mantém acesso do proprietário e SYSTEM, concede leitura/execução aos SIDs de teste em áreas autorizadas e nega acesso ao SID de pacote e Restricted Code em protected/.

Somente caminhos criados por essa instância, resolvidos e contidos na própria raiz, recebem SetFileSecurityW. A prova completa de leitura/escrita/listagem negadas depende de o probe conseguir iniciar sob a identidade restrita. Nesta máquina isso falhou antes das operações de arquivo. Os bytes dos canários foram preservados. A classificação resultante é FILESYSTEM_ISOLATION_NOT_VERIFIED.

O teste de rede cria listener TCP em 127.0.0.1 com porta efêmera. Supervisor e controle JOB_ONLY conectam. A tentativa APPCONTAINER falha antes do probe. O teste registra ausência de conexões recebidas nessa tentativa, mas o bloqueio de loopback continua NOT_VERIFIED. TCP externo, DNS, serviços privados reais e IPC permanecem NETWORK_EGRESS_NOT_VERIFIED. O tráfego é sintético, e os sockets não transmitem canários.

## Evidência e rollback

`--suite` retorna controles produzidos pelo supervisor com nome, hashes das políticas solicitadas, API, estado de configuração, estado de verificação, teste, observação, indicação de dados sintéticos, limitações e motivo de falha. Amostras contêm estado do processo, exit code inclusive após terminação, erro Win32, política, associação antes do resume, bytes, pico do Job e rollback. stdout bruto fica fora do relatório da suíte. Um worker que imprime ENFORCED_AND_TESTED não modifica esses campos.

Child assume ownership dos handles de processo/thread imediatamente após a criação, incluindo falhas antes da associação. Recursos nativos e streams possuem liberação explícita. O supervisor termina o Job, aguarda a lista de processos esvaziar e os handles sinalizarem, fecha pipes, processo, thread, tokens e Job. PocEnvironment libera SID e remove a árvore. Rollback incompleto prevalece sobre o resultado funcional e é retornado como ROLLBACK_INCOMPLETE. A morte abrupta do helper de teste é verificada por handles dos seus processos, enquanto o teste pai conserva ownership da árvore temporária para removê-la.

Falhas de criação/configuração/associação, DACL, escrita, interrupção e liberação são injetadas somente nas fixtures. O teste de interrupção aceita propagação de KeyboardInterrupt após limpeza. O teste de cleanup interrompido restaura o método e executa nova limpeza da mesma raiz conhecida. Quatro reexecuções normais conferem contagem de handles sem crescimento.

## Uso e limites

```powershell
.venv/Scripts/python -m cryptolab.research.ai_boundary.isolation_poc
.venv/Scripts/python -m cryptolab.research.ai_boundary.isolation_poc --run
.venv/Scripts/python -m cryptolab.research.ai_boundary.isolation_poc --suite
```

O primeiro comando faz discovery. O segundo tenta um probe de token APPCONTAINER e retorna código 2 nesta máquina. O terceiro executa experimentos explicitamente identificados e retorna PARTIAL_POC com código 0 quando o ensaio parcial e seu rollback terminam corretamente. Essa saída distingue conclusão do experimento de comprovação de todas as fronteiras.

CPU e disco ficam DEFERRED. JOB_ONLY conserva permissões e rede do usuário, com exceção dos limites de Job. O runtime copiado e o supervisor são confiáveis. Alteração concorrente desses arquivos por processo do mesmo usuário permanece fora da contenção. A demonstração usa fixtures fixas e não oferece um executor público ou um ambiente para código hostil.

A próxima etapa mínima proposta é uma revisão autorizada de criação/remoção de perfil AppContainer descartável, compatibilidade do runtime, ACL e testes reais de negação de arquivos e loopback. A criação do perfil ficou adiada por envolver estado persistente reservado pelo pedido para autorização futura. READY_FOR_D3B_REVIEW continua pendente dessas provas.

Após o reforço final de rollback, uma instância com falha nativa de limpeza bloqueia novos launches e conserva ROLLBACK_INCOMPLETE mesmo se a árvore temporária for removida. O teste de falha de diretório permite repetir a limpeza da mesma raiz conhecida após restaurar o método, pois essa falha é distinguida da falha nativa. A execução Windows posterior verifica ambos os casos. Acesso do processo JOB_ONLY ao supervisor e duplicação de handles por código hostil permanecem NOT_VERIFIED.
