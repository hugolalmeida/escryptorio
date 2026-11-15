# Capacidades Windows observadas · 2.3D3A.1

Discovery realizada em 15/11/2026, na branch main, a partir de `775e9c553d6ba346f23fceb1348345fc7eb30035`, com working tree limpo. As execuções da venv precisaram da identidade proprietária fora da restrição da ferramenta. O token Windows foi consultado e a PoC exige explicitamente TokenIsElevated=False. A permissão de ferramenta utilizada não ativou elevação UAC.

| Capacidade | Estado | Observação desta execução |
| --- | --- | --- |
| Windows e arquitetura | AVAILABLE | Windows 11 Home 10.0.26200 x64, ponteiros de 8 bytes, Python 3.10.11 |
| Virtualização de firmware e SLAT | AVAILABLE | Ambos reportados True por Win32_Processor |
| Hipervisor | UNAVAILABLE nesta observação | HypervisorPresent=False |
| Token primário | AVAILABLE | TokenType=1, TokenElevationType=3, elevado=False, AppContainer=False |
| Privilégios efetivos | AVAILABLE para consulta | Cinco presentes, um habilitado. SIDs e nomes de usuário ficam fora do diagnóstico |
| Criação/configuração de Job | AVAILABLE | CreateJobObjectW e SetInformationJobObject, com conferência por QueryInformationJobObject |
| Memória e processos | AVAILABLE | Alocação nativa limitada e tentativa de descendente negada em controles pareados |
| Kill on Job close | AVAILABLE | Teste encerra supervisor próprio e aguarda os handles dos dois processos pertencentes à fixture |
| Restricted Token | AVAILABLE para criação | CreateRestrictedToken com DISABLE_MAX_PRIVILEGE e SID Restricted Code. Launcher criou processo, cujo runtime encerrou com 0xC0000022 |
| AppContainer sem perfil | NOT_VERIFIED para execução | SID derivado, capabilities vazias e atributos configurados. CreateProcessW retornou erro 203 |
| Perfil AppContainer | REQUIRES_APPROVAL | Fluxo documentado cria perfil persistente. Esta tarefa reserva alterações persistentes para autorização futura |
| DACL sintética | AVAILABLE para configuração | SetFileSecurityW aplicado somente à árvore descartável da PoC. A negação de leitura pelo worker permanece NOT_VERIFIED |
| Loopback | AVAILABLE no controle positivo | Supervisor e JOB_ONLY alcançaram listener efêmero local |
| Negação de rede | NOT_VERIFIED | Tentativa AppContainer falhou no lançamento. TCP externo, DNS e IPC não foram exercitados |
| Firewall | AVAILABLE para consulta | Perfis Domain, Private e Public habilitados. Zero regras criadas ou alteradas pela PoC |
| Windows Sandbox / Hyper-V | NOT_VERIFIED nesta fase | Limitações de edição e discovery anterior documentadas na 2.3D3A. Recursos opcionais ficaram fora das novas alterações |

O diagnóstico local pode ser repetido com `.venv/Scripts/python -m cryptolab.research.ai_boundary.isolation_poc`. Ele consulta o token e cria/libera um token restrito efêmero para verificar a API. Arquivos, perfis, contas e políticas persistentes têm zero alterações nesse comando.

As assinaturas ctypes têm tipos de ponteiro explícitos, retornos checados e GetLastError nos caminhos de erro. Os tamanhos x64 são verificados para estruturas de Job, contabilidade, startup, processo, SID, atributos e capabilities. TokenElevation exige buffer de quatro bytes no ambiente observado. As primeiras consultas genéricas falharam com ERROR_BAD_LENGTH, registradas durante a investigação e corrigidas antes dos testes finais.

| Alternativa | Benefício observado | Dependências e complexidade | Decisão |
| --- | --- | --- | --- |
| Job Object + processo suspenso | Memória, número de processos, árvore e ciclo de vida exercitados pelo SO | APIs Win32 e runtime Python local, complexidade moderada | IMPLEMENTED para fixtures benignas |
| Restricted Token + DACL | Token e processo restrito criados | Compatibilidade do runtime/loader e desktop ainda sem prova | Launcher experimental IMPLEMENTED, execução FAILED |
| AppContainer com SID derivado | Preparação de atributos e DACL sintética funcionou | Processo sem perfil falhou com erro 203 | Tentativa FAILED, arquivos/rede NOT_VERIFIED |
| AppContainer com perfil | Fluxo oficial oferece identidade e diretórios próprios | Perfil persistente, autorização específica e rollback adicional | DEFERRED, REQUIRES_APPROVAL |
| Sandbox/VM/Docker | Fronteira alternativa para investigação futura | Disponibilidade, instalação/configuração e edição do Windows | DEFERRED |

A Microsoft documenta que Restricted Tokens realizam duas verificações de acesso, e que o launcher pode usar uma versão restrita do próprio token. Privilégios e sucesso de inicialização precisam ser verificados em cada ambiente. [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken), [CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw).

O fluxo oficial de AppContainer inclui criação de perfil e configuração do atributo SECURITY_CAPABILITIES. A tentativa desta PoC derivou somente um SID, sem criar o perfil. O erro observado delimita essa tentativa específica. [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer), [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).


# Prepara??o AppContainer ? 2.3D3A.2

Etapa n?o persistente conclu?da como PREPARATION_COMPLETE_AWAITING_APPROVAL. DACLs sint?ticas s?o capturadas antes das altera??es e conferidas ap?s aplica??o. Lifecycle e evid?ncia fechada foram preparados com testes mockados. Perfil real permanece NOT_AUTHORIZED, sem adapter nativo ou execu??o de CreateAppContainerProfile. Erro 203 e runtime 0xC0000022 foram reproduzidos, com causas espec?ficas ainda n?o confirmadas. Plano e testes em [AI_APPCONTAINER_APPROVAL_PLAN.md](AI_APPCONTAINER_APPROVAL_PLAN.md), [AI_APPCONTAINER_COMPATIBILITY.md](AI_APPCONTAINER_COMPATIBILITY.md) e [AI_ISOLATION_COMPATIBILITY_TESTS.md](AI_ISOLATION_COMPATIBILITY_TESTS.md). ISOLATED_RESEARCH permanece indispon?vel.
