# Isolamento de pesquisa · 2.3D3A

## Resultado e ambiente observado

**NOT_READY para um experimento D3B com modelo real.** O subconjunto determinístico e mock foi implementado. ISOLATED_RESEARCH falha fechado antes de reservar orçamento ou iniciar processo. DEVELOPMENT_MOCK exige seleção explícita e devolve NOT_SANDBOXED.

Consultas locais somente leitura em 15/11/2026 encontraram Windows 11 Home 64 bits, versão 10.0.26200, Python 3.10.11 64 bits. Win32_ComputerSystem reportou HypervisorPresent=False. O processador reportou VirtualizationFirmwareEnabled=True, SLAT=True e VMMonitorModeExtensions=True. Essas propriedades descrevem capacidade reportada pelo sistema.

WindowsSandbox.exe e docker.exe não foram encontrados por Get-Command no PATH consultado. Consultas individuais Get-WindowsOptionalFeature para Containers-DisposableClientVM e Microsoft-Hyper-V-All ficaram QUERY_UNAVAILABLE na identidade de execução. A primeira consulta teve também erro de sintaxe por fornecer array a FeatureName, corrigido na consulta individual. O estado efetivo dos recursos opcionais permanece NOT_VERIFIED. Windows Sandbox tem suporte documentado em edições específicas, com Home fora delas. [Microsoft Learn](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/).

Perfis Domain, Private e Public do firewall foram reportados habilitados. Política de egress por processo e loopback permanece NOT_VERIFIED. A ACL do diretório do projeto reportou AreAccessRulesProtected=False. Não foi criada ACL exclusiva para worker. A execução de ferramentas fora da identidade restrita da sessão foi necessária para usar a venv e o Git pertencentes ao usuário. Isso não constitui teste de um sandbox próprio do produto.

## Prova de conceito e matriz

Antes de qualquer integração de isolamento forte, uma prova mínima ctypes criou e fechou um Job Object anônimo. CreateRestrictedToken, CreateAppContainerProfile e InitializeProcThreadAttributeList foram encontrados nas DLLs do Windows. O ensaio comprova criação/fechamento do objeto e presença de símbolos. Aplicação de limites, lançamento restrito e bloqueio de acesso continuam NOT_VERIFIED. Nenhuma política persistente do Windows foi alterada.

| Opção | Segurança efetiva | Complexidade | Dependências | Limitações | Testabilidade | Recomendação |
| --- | --- | --- | --- | --- | --- | --- |
| Subprocesso fixo supervisionado | Prazo, quotas de mensagem e encerramento do filho direto TESTED | Baixa | Python stdlib | Permissões do usuário, FS/rede acessíveis conforme SO | Mock e falhas locais testados | IMPLEMENTED para DEVELOPMENT_MOCK |
| Restricted Token + ACL + Job Object | Recursos do SO DOCUMENTED, criação/fechamento Job TESTED | Alta | Win32, DACL, token e launcher auditado | Exige configuração e testes específicos de cada fronteira, egress adicional | Limites e acessos ainda NOT_VERIFIED | DEFERRED |
| AppContainer + Job Object | Isolamento granular DOCUMENTED | Alta | Perfil, capabilities, ACL da venv e launcher | Compatibilidade Python, loopback, objetos e recursos precisam de testes | Presença de API TESTED, contenção NOT_VERIFIED | PROPOSED como investigação futura |
| Windows Sandbox / VM | Kernel separado DOCUMENTED para Sandbox | Alta | Edição suportada, virtualização e transporte mínimo | Home encontrada, ausência de hipervisor ativo e launcher no PATH | Ambiente não foi iniciado | DEFERRED |
| Docker / outro ambiente | Nenhuma propriedade local demonstrada | Alta | Runtime e configuração próprios | Launcher ausente no PATH consultado | NOT_VERIFIED | DEFERRED |

Job Objects gerenciam conjuntos de processos e limites de recursos. A segurança individual exige controles adicionais. Restricted Tokens restringem privilégios e acesso a objetos conforme o token/DACL. AppContainer oferece mecanismos de isolamento de credenciais, arquivos, rede e processos que ainda precisam ser configurados e testados nesta aplicação. [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [Restricted Tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens), [AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation).

## Controles por fronteira

| Fronteira | Estado nesta entrega |
| --- | --- |
| Supervisão | IMPLEMENTED e TESTED para filho direto, timeout, cancelamento, exit code e quotas stdout/stderr |
| Memória, CPU, disco e descendentes | DEFERRED, sem limite integrado de SO |
| Arquivos e ledger | Minimização de payload IMPLEMENTED e TESTED. Negação de leitura/gravação pelo SO NOT_VERIFIED |
| Rede externa, DNS e loopback | Bloqueio por worker DEFERRED e NOT_VERIFIED |
| Ambiente | Allowlist de TEMP/TMP/SystemRoot IMPLEMENTED. Canário sintético de ambiente ausente no filho TESTED |
| Execução | Comando fixo, sem shell, sem interpretação de texto e sem imports financeiros no script mock IMPLEMENTED e TESTED no fluxo funcional. Negação de comandos arbitrários pelo SO NOT_VERIFIED |

O processo Python pode alcançar arquivos e rede conforme as permissões do usuário. `-I -S`, ambiente mínimo e diretório temporário têm finalidade de previsibilidade e minimização. A ausência de capacidade de ler credenciais ou ledger permanece sem comprovação de SO. O modo isolado indisponível impede executar um modelo futuro por esse caminho.

## Threat model e canários

Ativos relevantes são bundles originais, dados financeiros, arquivos privados, ambiente e serviços locais. Entradas não confiáveis incluem bundles, claims, warnings e respostas do filho. O builder e o supervisor são componentes confiáveis executados pelo operador. Processo concorrente com permissões do usuário pode modificar código ou arquivos e está fora da contenção implementada.

Testes usam .env.synthetic temporário, variáveis FAKE_EXCHANGE_API_KEY, strings FAKE_PRIVATE_TOKEN e FAKE_LEDGER_CANARY. Conferem ausência nos contextos/outputs e na saída capturada, exclusão de warnings privados, rejeição de campos/caminhos e operações de leitura de banco, segredos, executor e chamada externa. Esses últimos são tentativas simuladas pelo contrato, com falha antes de qualquer ação. A ausência do canário de ambiente é também testada por processo real benigno com ambiente explícito.

Os testes de gateway recusam respostas adulteradas mesmo com output_hash recalculado. O teste de não mutação compara dump integral do SQLite sintético e bytes de cada arquivo do bundle antes/depois. Muitas tabelas paper/monitor estão vazias nessa fixture. Nenhum teste lê .env pessoal ou credenciais reais. Nenhum payload hostil é executado como código. Negação real de acesso a arquivos pessoais, ledger, HTTP, DNS, TCP ou serviço privado permanece NOT_VERIFIED. Nenhuma conexão de exfiltração real foi realizada.

## Riscos residuais e gate

Riscos residuais incluem acesso do subprocesso às permissões do usuário, ausência de limite de memória/CPU/disco, ausência de kill-on-supervisor-exit, corridas em arquivos controlados pelo mesmo usuário, autenticidade externa desconhecida, incompatibilidade com v1 no novo builder e ausência de validação de linguagem livre. A inspeção de APIs e testes de mock não autorizam execução de código hostil.

O futuro gate exige launcher com fronteiras de SO comprovadas para arquivos, credenciais, rede/loopback, memória e árvore de processos. Também exige política de privacidade, retenção, fornecedor, orçamento e aceitação humana dos riscos residuais. Essas decisões estão pendentes. A fase 2.3D3B continua fora desta entrega.

# Prova Windows · 2.3D3A.1

A PoC experimental implementa processo suspenso, Job configurado e conferido antes do resume, limites de commit/processos, término da árvore e rollback. O teste de morte do supervisor comprova KILL_ON_JOB_CLOSE nas fixtures benignas. O resultado é PARTIAL_POC. Restricted Token criou processo, mas o runtime falhou na inicialização; AppContainer sem perfil falhou na criação. Negação de filesystem e rede permanece NOT_VERIFIED. ISOLATED_RESEARCH conserva falha fechada, e JOB_ONLY é seleção explícita exclusiva dos experimentos de recursos.

Capacidades observadas em [WINDOWS_ISOLATION_CAPABILITIES.md](WINDOWS_ISOLATION_CAPABILITIES.md). Launcher, política e rollback em [AI_WINDOWS_ISOLATION_POC.md](AI_WINDOWS_ISOLATION_POC.md). Evidências, limitações e próxima etapa em [AI_ISOLATION_TEST_RESULTS.md](AI_ISOLATION_TEST_RESULTS.md).


# Prepara??o AppContainer ? 2.3D3A.2

Etapa n?o persistente conclu?da como PREPARATION_COMPLETE_AWAITING_APPROVAL. DACLs sint?ticas s?o capturadas antes das altera??es e conferidas ap?s aplica??o. Lifecycle e evid?ncia fechada foram preparados com testes mockados. Perfil real permanece NOT_AUTHORIZED, sem adapter nativo ou execu??o de CreateAppContainerProfile. Erro 203 e runtime 0xC0000022 foram reproduzidos, com causas espec?ficas ainda n?o confirmadas. Plano e testes em [AI_APPCONTAINER_APPROVAL_PLAN.md](AI_APPCONTAINER_APPROVAL_PLAN.md), [AI_APPCONTAINER_COMPATIBILITY.md](AI_APPCONTAINER_COMPATIBILITY.md) e [AI_ISOLATION_COMPATIBILITY_TESTS.md](AI_ISOLATION_COMPATIBILITY_TESTS.md). ISOLATED_RESEARCH permanece indispon?vel.


# Native lifecycle preparation 2.3D3A.3

PREPARATION_COMPLETE_AWAITING_APPROVAL. Native read-only adapter and blocked mutation interfaces prepared. ProfileLifecycle supports an optional durable journal for synthetic tests. Recovery is inspection-only and uncertain ownership requires manual review. Reserved profile was absent in inspected storage/registry locations. No profile creation/deletion executed. See [native lifecycle](AI_APPCONTAINER_NATIVE_LIFECYCLE.md), [recovery](AI_APPCONTAINER_RECOVERY.md) and [authorized test plan](AI_APPCONTAINER_AUTHORIZED_TEST_PLAN.md). Filesystem/network enforcement remains NOT_VERIFIED; ISOLATED_RESEARCH remains unavailable.
