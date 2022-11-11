from django.contrib import admin

from .models import Aluno, NotaAluno, DataAttNota

# Register your models here.

admin.site.register(Aluno)
admin.site.register(NotaAluno)
admin.site.register(DataAttNota)