<!-- Card para Emissão de Relatório Fotográfico -->
<div class="card" style="margin-top: 20px;">
    <h2>Emitir Relatório Técnico com Fotos</h2>
    <form id="formRelatorio" enctype="multipart/form-data">
        
        <div class="grid">
            <div>
                <label><strong>Título do Relatório:</strong></label>
                <input type="text" id="relTitulo" placeholder="Ex: Vistoria de Fachada e Infiltrações" required>
            </div>
            <div>
                <label><strong>Cliente / Condomínio:</strong></label>
                <input type="text" id="relCliente" placeholder="Ex: Condomínio Parque São Rafael" required>
            </div>
        </div>

        <div class="grid">
            <div>
                <label><strong>Local da Inspeção:</strong></label>
                <input type="text" id="relLocal" placeholder="Ex: Rua Santo André Avelino, 191 - SP">
            </div>
            <div>
                <label><strong>Data da Vistoria:</strong></label>
                <input type="date" id="relData" required>
            </div>
        </div>

        <div style="margin-top: 15px;">
            <label><strong>Considerações Técnicas / Diagnóstico:</strong></label>
            <textarea id="relObservacoes" rows="4" style="width:100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;" placeholder="Descreva os achados técnicos, apontamentos de patologias e recomendações..."></textarea>
        </div>

        <!-- Seção de Fotos -->
        <div style="margin-top: 20px; border-top: 1px solid #eee; padding-top: 15px;">
            <h3>Anexar Fotos e Apontamentos</h3>
            <p style="font-size: 13px; color: #666;">Selecione as imagens do laudo/vistoria e adicione a legenda correspondente a cada uma.</p>

            <div id="containerFotos">
                <!-- Linha dinâmica de foto -->
                <div class="item-foto" style="display: flex; gap: 10px; margin-bottom: 10px; align-items: center;">
                    <input type="file" class="inputFoto" accept="image/*" required style="width: 40%;">
                    <input type="text" class="inputLegenda" placeholder="Descrição / Legenda da Foto (Ex: Fissura em viga do bloco B)" required style="width: 55%;">
                    <button type="button" onclick="removerFoto(this)" style="width: 5%; background: #e53e3e; color: white;">X</button>
                </div>
            </div>

            <button type="button" onclick="adicionarCampoFoto()" style="background: #4a5568; margin-top: 5px;">+ Adicionar Outra Foto</button>
        </div>

        <button type="submit" style="margin-top: 20px; background: #2b6cb0; font-size: 16px; padding: 12px;">
            Gerar Relatório Fotográfico em PDF
        </button>
    </form>
</div>

<script>
    // Define a data atual como padrão no campo de data
    document.getElementById('relData').valueAsDate = new Date();

    // Função para adicionar dinamicamente novos campos de foto
    function adicionarCampoFoto() {
        const container = document.getElementById('containerFotos');
        const novaLinha = document.createElement('div');
        novaLinha.className = 'item-foto';
        novaLinha.style = 'display: flex; gap: 10px; margin-bottom: 10px; align-items: center;';
        
        novaLinha.innerHTML = `
            <input type="file" class="inputFoto" accept="image/*" required style="width: 40%;">
            <input type="text" class="inputLegenda" placeholder="Descrição / Legenda da Foto" required style="width: 55%;">
            <button type="button" onclick="removerFoto(this)" style="width: 5%; background: #e53e3e; color: white;">X</button>
        `;
        
        container.appendChild(novaLinha);
    }

    // Função para remover uma linha de foto
    function removerFoto(botao) {
        const container = document.getElementById('containerFotos');
        if (container.children.length > 1) {
            botao.parentElement.remove();
        } else {
            alert("É necessário manter pelo menos um campo de foto.");
        }
    }

    // Envio do formulário via FormData para a API Node.js
    document.getElementById('formRelatorio').addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData();
        formData.append('titulo', document.getElementById('relTitulo').value);
        formData.append('cliente', document.getElementById('relCliente').value);
        formData.append('local', document.getElementById('relLocal').value);
        formData.append('data', document.getElementById('relData').value);
        formData.append('observacoes', document.getElementById('relObservacoes').value);

        // Coleta todas as fotos e suas respectivas legendas
        const linhasFotos = document.querySelectorAll('.item-foto');
        linhasFotos.forEach(linha => {
            const fileInput = linha.querySelector('.inputFoto');
            const legendaInput = linha.querySelector('.inputLegenda');

            if (fileInput.files[0]) {
                formData.append('fotos', fileInput.files[0]);
                formData.append('descricoesFotos', legendaInput.value);
            }
        });

        try {
            // Requisição para a API Node.js
            const response = await fetch('http://localhost:3000/api/relatorios/pdf', {
                method: 'POST',
                body: formData // Envia no formato multipart/form-data
            });

            if (response.ok) {
                // Recebe o PDF como blob e abre em uma nova aba
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                window.open(url, '_blank');
            } else {
                alert('Erro ao gerar o relatório em PDF.');
            }
        } catch (error) {
            console.error('Erro na requisição:', error);
            alert('Falha na conexão com o servidor Node.js.');
        }
    });
</script>
