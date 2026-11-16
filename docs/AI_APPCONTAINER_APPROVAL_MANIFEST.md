# Atualização · 2.3D3A.4-BRIDGE — NOT_AUTHORIZED

Perfil/política/operação abaixo continuam apenas proposta, sem execução. [Bridge preparado](AI_APPCONTAINER_NATIVE_BRIDGE.md) e [recibos do Windows](AI_APPCONTAINER_OS_RECEIPTS.md) foram implementados e testados com recursos benignos; fachada de mutação só exercitada com FakeUserenv. Nenhum caminho normal instancia a fachada nativa ou fornece API ao bridge. A futura decisão exige revisão do commit e riscos residuais, autorização humana específica, nome/política exatos, rollback revisado e tarefa separada para conexão/ensaio. Nenhum manifesto, JSON, ambiente, marcador ou status habilita execute_authorized_test. Nova inspeção somente leitura encontrou pasta/mapeamento ausentes, sem prova de ownership ou ausência universal. Root operacional de journals continua inexistente.

# Revisão 2.3D3A.4-GATE — PREFLIGHT_PARTIAL

**NOT_AUTHORIZED.** Perfil, política e operação propostos abaixo permanecem apenas identificadores da proposta. [Preflight final](AI_APPCONTAINER_FINAL_PREFLIGHT.md) e [rollback](AI_APPCONTAINER_ROLLBACK_VERIFICATION.md) registram os limites atuais. A próxima decisão é revisar o commit e definir a preparação faltante do bridge e dos coletores nativos. Nenhum campo deste manifesto, ambiente ou status de mock autoriza conexão/execução. O local persistente de journal não foi criado. Antes de eventual Create, será obrigatório verificar sua DACL/owner/caminho com o guard, conferir novamente perfil ausente e registrar intenção durável; autorização humana futura exige nova tarefa, perfil/política exatos e rollback revisado. A ausência observada nesta fase é limitada ao storage e mapeamento exatos, sem recibo de ownership.

# Manifesto para revisão humana · NOT_AUTHORIZED

Este documento descreve uma operação proposta. Ele não concede autorização nem funciona como credencial de execução.

| Campo | Valor planejado |
| --- | --- |
| Perfil exato | Escryptorio.PoC.D3A2.20261115.8c514dea |
| Policy ID | 489b6c6abe0719cd8cc78a8cf18fbe1159235ed5be69dc72312f5359fc62258b |
| Operação proposta | 230c1bce76cfa4401ddfaff1168eb46a9deefb525c13a5b99d7f91203682d788 |
| Capabilities | Vazio |
| Runtime | Python GUI conhecido, DLLs e stdlib na árvore própria, sem site-packages ou módulos financeiros |
| Diretórios | protected, allowed, worker, outputs na árvore temporária exclusiva |
| Arquivos | Canários sintéticos, SQLite fictício, contexto mínimo, runtime e outputs sintéticos |
| Memória | 67.108.864 bytes por processo, 100.663.296 por Job |
| Processos e tempo | Um processo, três segundos; quotas stdout/stderr anteriores de 65.536 bytes |
| Journal proposto | %LOCALAPPDATA%/Escryptorio/IsolationPoC/journals, volume local e DACL a verificar |
| Estado atual | PROFILE_CREATION_REQUIRES_APPROVAL |

Inspeção atual read-only encontrou folder_present=False, mapping_present=False e ABSENT_IN_INSPECTED_LOCATIONS. Isso não prova ausência universal de resíduos. Reinspecionar imediatamente antes de qualquer criação e abortar colisão, sem reuso ou exclusão de terceiros. SID esperado será derivado e confrontado com o retorno da API, sem inferir ownership apenas pela derivação.

As operações persistentes propostas são CreateAppContainerProfile para um único perfil per-user/per-app e seu registro/armazenamento, escrita de journal/manifesto de operação, e DeleteAppContainerProfile exclusivamente para o perfil próprio verificado. As strings e o SID alocados exigem CoTaskMemFree/FreeSid correspondentes. DeriveAppContainerSidFromAppContainerName, GetAppContainerFolderPath e consultas ao mapeamento exato são somente leitura.

O processo supervisor deverá usar token primário limitado, sem solicitação automática de administrador. Qualquer necessidade de elevação interrompe o procedimento para nova decisão. Antes de retomar o filho, confirmar Job configurado, associação, IsProcessInJob e herança limitada aos pipes. Job handle fica fora da herança. Preparar ACLs somente na árvore própria, com runtime RX, allowed R, outputs com escrita mínima e protected negado. O supervisor deve manter controle de limpeza e proteger o journal contra a identidade AppContainer.

Os testes futuros verificam identidade, runtime inicializado, leitura permitida, leitura/escrita/listagem protegidas negadas por códigos OS, escrita em outputs e integridade dos canários. Listener local efêmero permite controles positivos do supervisor/JOB_ONLY e tentativa AppContainer. O listener registra conexões e o probe registra erros. Ausência de conexão com runtime falho permanece NOT_VERIFIED. Internet, DNS e IPC requerem provas separadas, sem tráfego externo neste ensaio.

Rollback exige término dos processos, espera dos handles, liberação de recursos, conferência conjunta de nome/política/operação/SIDs/journal/estado externo, exclusão via API e verificação de ausência nas localizações conhecidas. A árvore própria deve ser removida e conferida antes de CLEANED. A existência de journal ou sucesso de Delete isolados não bastam. Recursos ambíguos ficam para revisão manual, sem limpeza por prefixo ou edição manual do registro.

Riscos residuais incluem perfil/registro/diretórios/journal residuais, resposta perdida da API, crash antes da confirmação do SID, falha de fsync/replace/read-back, incompatibilidade do loader, permissões de desktop/DLL e controle malicioso do mesmo usuário sobre arquivos do supervisor. Recuperação começa por inspeção read-only. ROLLBACK_INCOMPLETE prevalece sobre sucesso do probe. Nenhum perfil real ou journal real de perfil foi criado nesta tarefa.

A próxima decisão humana é autorizar especificamente esse perfil, capabilities vazias, uma árvore sintética com Job limitado e listener local, remoção do perfil de ownership comprovado e verificação de resíduos. A aprovação deve ocorrer em outra interação, após revisão deste manifesto e do código. O bridge operacional nativo ainda precisará ser revisado explicitamente. O ensaio não autoriza LLM, D3B ou execução financeira.
