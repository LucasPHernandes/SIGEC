// Sistema de temas
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.init();
    }

    init() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateButton();
        
        document.getElementById('themeToggle')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggle();
        });
    }

    toggle() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.theme);
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateButton();
        
        // Animação suave de transição
        document.body.style.transition = 'background-color 0.3s, color 0.3s';
        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);
    }

    updateButton() {
        const button = document.getElementById('themeToggle');
        if (button) {
            const icon = button.querySelector('i');
            const text = button.querySelector('span');
            
            if (this.theme === 'light') {
                icon.className = 'fas fa-moon';
                text.textContent = 'Tema Escuro';
            } else {
                icon.className = 'fas fa-sun';
                text.textContent = 'Tema Claro';
            }
        }
    }
}

// Gerenciamento da sidebar
class SidebarManager {
    constructor() {
        this.sidebar = document.getElementById('sidebar');
        this.mainContent = document.getElementById('mainContent');
        this.toggleBtn = document.getElementById('sidebarToggle');
        this.mobileToggle = document.getElementById('mobileMenuToggle');
        
        this.isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        this.isMobile = window.innerWidth <= 768;
        
        this.init();
    }

    init() {
        if (this.isMobile) {
            this.sidebar?.classList.remove('collapsed');
        } else if (this.isCollapsed) {
            this.sidebar?.classList.add('collapsed');
        }
        
        this.toggleBtn?.addEventListener('click', () => this.toggle());
        this.mobileToggle?.addEventListener('click', () => this.toggleMobile());
        
        window.addEventListener('resize', () => this.handleResize());
        
        // Fecha sidebar ao clicar fora no mobile
        document.addEventListener('click', (e) => {
            if (this.isMobile && 
                this.sidebar?.classList.contains('active') &&
                !this.sidebar.contains(e.target) &&
                !this.mobileToggle.contains(e.target)) {
                this.sidebar.classList.remove('active');
            }
        });
    }

    toggle() {
        if (this.isMobile) return;
        
        this.sidebar?.classList.toggle('collapsed');
        localStorage.setItem('sidebarCollapsed', this.sidebar?.classList.contains('collapsed'));
        
        // Animação para ícones
        this.animateIcons();
    }

    toggleMobile() {
        this.sidebar?.classList.toggle('active');
        document.body.style.overflow = this.sidebar?.classList.contains('active') ? 'hidden' : '';
    }

    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth <= 768;
        
        if (wasMobile !== this.isMobile) {
            if (this.isMobile) {
                this.sidebar?.classList.remove('collapsed', 'active');
                document.body.style.overflow = '';
            } else {
                if (this.isCollapsed) {
                    this.sidebar?.classList.add('collapsed');
                }
            }
        }
    }

    animateIcons() {
        const icons = this.sidebar?.querySelectorAll('i');
        icons?.forEach(icon => {
            icon.style.transform = 'scale(0.8)';
            setTimeout(() => {
                icon.style.transform = '';
            }, 200);
        });
    }
}

// Gerenciamento de notificações
class NotificationManager {
    constructor() {
        this.notifications = [];
        this.container = this.createContainer();
    }

    createContainer() {
        let container = document.getElementById('notificationContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notificationContainer';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(container);
        }
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} animate-slide-in-right`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas ${this.getIcon(type)}"></i>
                <span>${message}</span>
            </div>
            <button class="notification-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Estilos da notificação
        notification.style.cssText = `
            background: var(--bg-primary);
            border-left: 4px solid var(--${type});
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            padding: 12px 16px;
            min-width: 300px;
            max-width: 400px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            animation: slideInRight 0.3s ease;
        `;
        
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => this.close(notification));
        
        if (duration > 0) {
            setTimeout(() => this.close(notification), duration);
        }
        
        this.container.appendChild(notification);
        this.notifications.push(notification);
        
        return notification;
    }

    close(notification) {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
            this.notifications = this.notifications.filter(n => n !== notification);
        }, 300);
    }

    getIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            danger: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }
}

// Gerenciamento de modais
class ModalManager {
    constructor() {
        this.modals = [];
    }

    create(options = {}) {
        const {
            title = '',
            content = '',
            size = 'md',
            showClose = true,
            closeOnOverlay = true
        } = options;
        
        const modalId = 'modal_' + Date.now();
        const modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal modal-${size}">
                <div class="modal-header">
                    <h3>${title}</h3>
                    ${showClose ? '<button class="modal-close"><i class="fas fa-times"></i></button>' : ''}
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                <div class="modal-footer">
                    <button class="btn btn-outline" data-action="cancel">Cancelar</button>
                    <button class="btn btn-primary" data-action="confirm">Confirmar</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Eventos
        const closeBtn = modal.querySelector('.modal-close');
        closeBtn?.addEventListener('click', () => this.close(modalId));
        
        if (closeOnOverlay) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.close(modalId);
                }
            });
        }
        
        // Botões de ação
        modal.querySelector('[data-action="cancel"]')?.addEventListener('click', () => {
            this.close(modalId);
            options.onCancel?.();
        });
        
        modal.querySelector('[data-action="confirm"]')?.addEventListener('click', () => {
            this.close(modalId);
            options.onConfirm?.();
        });
        
        // Mostra com animação
        setTimeout(() => modal.classList.add('active'), 10);
        
        this.modals.push({ id: modalId, element: modal });
        
        return modalId;
    }

    close(modalId) {
        const modal = this.modals.find(m => m.id === modalId);
        if (modal) {
            modal.element.classList.remove('active');
            setTimeout(() => {
                modal.element.remove();
                this.modals = this.modals.filter(m => m.id !== modalId);
            }, 300);
        }
    }

    closeAll() {
        this.modals.forEach(modal => this.close(modal.id));
    }
}

// Gerenciamento de formulários
class FormManager {
    constructor(formElement) {
        this.form = formElement;
        this.fields = this.form.querySelectorAll('[data-validate]');
        this.init();
    }

    init() {
        this.form.addEventListener('submit', (e) => this.validate(e));
        this.fields.forEach(field => {
            field.addEventListener('input', () => this.clearError(field));
            field.addEventListener('blur', () => this.validateField(field));
        });
    }

    validate(e) {
        let isValid = true;
        
        this.fields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            this.showFirstError();
        }
        
        return isValid;
    }

    validateField(field) {
        const rules = field.dataset.validate.split(' ');
        let isValid = true;
        
        rules.forEach(rule => {
            const [ruleName, ruleValue] = rule.split(':');
            
            switch(ruleName) {
                case 'required':
                    if (!field.value.trim()) {
                        this.showError(field, 'Campo obrigatório');
                        isValid = false;
                    }
                    break;
                    
                case 'email':
                    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                    if (field.value && !emailRegex.test(field.value)) {
                        this.showError(field, 'Email inválido');
                        isValid = false;
                    }
                    break;
                    
                case 'min':
                    if (field.value.length < parseInt(ruleValue)) {
                        this.showError(field, `Mínimo de ${ruleValue} caracteres`);
                        isValid = false;
                    }
                    break;
                    
                case 'max':
                    if (field.value.length > parseInt(ruleValue)) {
                        this.showError(field, `Máximo de ${ruleValue} caracteres`);
                        isValid = false;
                    }
                    break;
                    
                case 'cpf':
                    const cpfRegex = /^\d{3}\.\d{3}\.\d{3}-\d{2}$/;
                    if (field.value && !cpfRegex.test(field.value)) {
                        this.showError(field, 'CPF inválido');
                        isValid = false;
                    }
                    break;
            }
        });
        
        if (isValid) {
            this.clearError(field);
        }
        
        return isValid;
    }

    showError(field, message) {
        field.classList.add('error');
        
        let errorElement = field.parentNode.querySelector('.form-error');
        if (!errorElement) {
            errorElement = document.createElement('span');
            errorElement.className = 'form-error';
            field.parentNode.appendChild(errorElement);
        }
        
        errorElement.textContent = message;
        
        // Animação de erro
        field.style.animation = 'shake 0.3s ease';
        setTimeout(() => {
            field.style.animation = '';
        }, 300);
    }

    clearError(field) {
        field.classList.remove('error');
        const errorElement = field.parentNode.querySelector('.form-error');
        if (errorElement) {
            errorElement.remove();
        }
    }

    showFirstError() {
        const firstError = this.form.querySelector('.error');
        if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstError.focus();
        }
    }
}

// Gerenciamento de gráficos
class ChartManager {
    constructor() {
        this.charts = new Map();
    }

    createLineChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId)?.getContext('2d');
        if (!ctx) return;
        
        const defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary')
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: 'rgba(0,0,0,0.1)'
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
                    }
                }
            }
        };
        
        const chart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: { ...defaultOptions, ...options }
        });
        
        this.charts.set(elementId, chart);
        return chart;
    }

    createBarChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId)?.getContext('2d');
        if (!ctx) return;
        
        const defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary')
                    }
                }
            },
            scales: {
                y: {
                    grid: {
                        color: 'rgba(0,0,0,0.1)'
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary')
                    }
                }
            }
        };
        
        const chart = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: { ...defaultOptions, ...options }
        });
        
        this.charts.set(elementId, chart);
        return chart;
    }

    createPieChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId)?.getContext('2d');
        if (!ctx) return;
        
        const defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary')
                    }
                }
            }
        };
        
        const chart = new Chart(ctx, {
            type: 'pie',
            data: data,
            options: { ...defaultOptions, ...options }
        });
        
        this.charts.set(elementId, chart);
        return chart;
    }

    updateTheme() {
        this.charts.forEach(chart => {
            const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-primary');
            const secondaryColor = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary');
            
            chart.options.plugins.legend.labels.color = textColor;
            
            if (chart.options.scales) {
                if (chart.options.scales.y) {
                    chart.options.scales.y.ticks.color = secondaryColor;
                }
                if (chart.options.scales.x) {
                    chart.options.scales.x.ticks.color = secondaryColor;
                }
            }
            
            chart.update();
        });
    }
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    // Inicializa gerenciadores
    window.themeManager = new ThemeManager();
    window.sidebarManager = new SidebarManager();
    window.notificationManager = new NotificationManager();
    window.modalManager = new ModalManager();
    window.chartManager = new ChartManager();
    
    // Fecha alertas
    document.querySelectorAll('.alert-close').forEach(btn => {
        btn.addEventListener('click', function() {
            const alert = this.closest('.alert');
            alert.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        });
    });
    
    // Auto-fecha alertas após 5 segundos
    document.querySelectorAll('.alert').forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => alert.remove(), 300);
            }
        }, 5000);
    });
    
    // Inicializa formulários com validação
    document.querySelectorAll('form[data-validate]').forEach(form => {
        new FormManager(form);
    });
    
    // Animações de entrada
    document.querySelectorAll('.card').forEach((card, index) => {
        card.style.animation = `slideIn 0.3s ease ${index * 0.1}s both`;
    });
    
    // Loading states
    document.querySelectorAll('[data-loading]').forEach(element => {
        element.addEventListener('click', function(e) {
            if (this.dataset.loading === 'true') {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Carregando...';
                this.disabled = true;
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 2000);
            }
        });
    });
    
    // Tooltips
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        element.addEventListener('mouseenter', function(e) {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.dataset.tooltip;
            tooltip.style.cssText = `
                position: absolute;
                background: var(--bg-primary);
                color: var(--text-primary);
                padding: 4px 8px;
                border-radius: var(--radius-sm);
                font-size: var(--font-size-sm);
                box-shadow: var(--shadow-md);
                z-index: 1000;
                pointer-events: none;
                animation: fadeIn 0.2s ease;
            `;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
            
            this.addEventListener('mouseleave', () => tooltip.remove(), { once: true });
        });
    });
});

// Animações de scroll
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-fade-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));