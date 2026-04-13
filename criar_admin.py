# criar_admin.py
from app import app, db, Usuario

with app.app_context():
    # Verifica se já existe admin
    admin = Usuario.query.filter_by(email='admin@iffar.edu.br').first()
    
    if admin:
        print(f"Admin já existe: {admin.nome}")
        print(f"Email: {admin.email}")
        print(f"Role: {admin.role}")
        print(f"Ativo: {admin.ativo}")
    else:
        # Cria novo admin
        admin = Usuario(
            nome='Administrador',
            email='admin@iffar.edu.br',
            role='admin',
            ativo=True
        )
        admin.set_senha('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin criado com sucesso!")
        print("Email: admin@iffar.edu.br")
        print("Senha: admin123")