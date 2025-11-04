import tkinter as tk
from .gui import AppPrincipal
import sys
import ctypes

def definir_nome_app(nome_app):
    """Define o nome da aplicação para o sistema operacional."""
    # Para Windows
    if sys.platform == 'win32':
        # Define o AppUserModelID para que o ícone e o nome corretos apareçam na barra de tarefas
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(nome_app)

def run_app():
    """Inicia e executa a aplicação principal."""
    APP_NAME = "Controle Financeiro"
    definir_nome_app(APP_NAME)

    from .database import restaurar_backup, USE_POSTGRES
    from tkinter import messagebox

    if not USE_POSTGRES:
        try:
            result = restaurar_backup()
            if result:
                # A mensagem de sucesso pode ser um pouco intrusiva a cada inicialização.
                # Vamos comentá-la por enquanto.
                # messagebox.showinfo("Sucesso", "Seus dados foram restaurados com sucesso!")
                pass
        except Exception as e:
            # Só fecha o app se for erro realmente inesperado (não "sem backup")
            msg = str(e).lower()
            if 'no such table' in msg or 'lancamentos_backup' in msg:
                pass  # ignora erro de não existir backup
            else:
                messagebox.showerror("Erro na Restauração",
                    f"Ocorreu um erro ao tentar restaurar seus dados.\n\n"
                    f"Erro: {str(e)}")
                sys.exit(1)

    root = tk.Tk()
    app = AppPrincipal(root)
    root.mainloop()

if __name__ == "__main__":
    run_app()