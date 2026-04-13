// Funções específicas para gráficos do dashboard
function initDashboardCharts() {
    // Gráfico de ocorrências por setor
    const setorData = {
        labels: ['Direção', 'Pedagógico', 'Assistência', 'Saúde', 'Secretaria'],
        datasets: [{
            label: 'Ocorrências por Setor',
            data: [12, 19, 8, 5, 7],
            backgroundColor: [
                '#00420C',
                '#0066B3',
                '#E30613',
                '#00A859',
                '#800080'
            ],
            borderWidth: 0,
            borderRadius: 8
        }]
    };
    
    window.chartManager.createBarChart('chartSetores', setorData, {
        plugins: {
            legend: {
                display: false
            }
        }
    });
    
    // Gráfico de status das ocorrências
    const statusData = {
        labels: ['Abertas', 'Em Andamento', 'Resolvidas', 'Canceladas'],
        datasets: [{
            data: [15, 8, 25, 3],
            backgroundColor: [
                '#FFC107',
                '#17A2B8',
                '#28A745',
                '#DC3545'
            ],
            borderWidth: 0
        }]
    };
    
    window.chartManager.createPieChart('chartStatus', statusData);
    
    // Gráfico de linha - tendência mensal
    const tendenciaData = {
        labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
        datasets: [{
            label: 'Ocorrências 2024',
            data: [10, 15, 12, 18, 22, 25],
            borderColor: '#00420C',
            backgroundColor: 'rgba(0, 66, 12, 0.1)',
            tension: 0.4,
            fill: true
        }]
    };
    
    window.chartManager.createLineChart('chartTendencia', tendenciaData);
}

// Atualiza gráficos com dados da API
async function updateChartsWithData() {
    try {
        const response = await fetch('/api/estatisticas');
        const data = await response.json();
        
        // Atualiza gráfico de ocorrências por mês
        if (data.ocorrencias_por_mes) {
            const meses = data.ocorrencias_por_mes.map(item => {
                const [ano, mes] = item.mes.split('-');
                return `${mes}/${ano}`;
            });
            const totais = data.ocorrencias_por_mes.map(item => item.total);
            
            const chart = window.chartManager.charts.get('chartTendencia');
            if (chart) {
                chart.data.labels = meses;
                chart.data.datasets[0].data = totais;
                chart.update();
            }
        }
        
        // Atualiza gráfico de alunos por turma
        if (data.alunos_por_turma) {
            const turmas = data.alunos_por_turma.map(item => item.turma);
            const totais = data.alunos_por_turma.map(item => item.total);
            
            const chart = window.chartManager.charts.get('chartSetores');
            if (chart) {
                chart.data.labels = turmas;
                chart.data.datasets[0].data = totais;
                chart.update();
            }
        }
        
    } catch (error) {
        console.error('Erro ao atualizar gráficos:', error);
    }
}

// Inicializa quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('chartSetores')) {
        initDashboardCharts();
        
        // Atualiza a cada 30 segundos
        setInterval(updateChartsWithData, 30000);
    }
});