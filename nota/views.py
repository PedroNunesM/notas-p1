import os
import requests
import json
import threading
import time
import datetime
import pytz
from django.shortcuts import redirect, render
from django.http import HttpResponse
from .models import Aluno, NotaAluno
from django.contrib import messages
import pandas as pd
from django.contrib.auth.decorators import user_passes_test

def setStudentDataOnDatabase(students):
	student_table = Aluno.objects.all()

	for student in students:
		if(not student_table.filter(id_huxley=student['id_huxley']).exists()):
			new_student = Aluno(nome=student['nome'], id_huxley=student['id_huxley'])
			new_student.save()

def setStudentScoreListOnDatabase(userScores, list_number):
	for userScore in userScores:
		student = Aluno.objects.get(id_huxley=userScore['id_huxley'])
		setattr(student, 'lista'+str(list_number), userScore['score'])
		student.save()
	
def setStudentScoreTestsOnDatabase(userScores, list_number):
	for userScore in userScores:
		student = Aluno.objects.get(id_huxley=userScore['id_huxley'])
		if userScore['id_huxley'] == 42148 and list_number == 1:
			userScore['score'] += 2.9
		elif userScore['id_huxley'] == 40528 and list_number == 1:
			userScore['score'] = 9.2
		setattr(student, 'prova'+str(list_number), userScore['score'])
		student.save()

def setStudentScoreTestsReassessmentsOnDatabase(userScores, list_number):
	for userScore in userScores:
		student = Aluno.objects.get(id_huxley=userScore['id_huxley'])
		if list_number == 1:
			setattr(student, 'reav', userScore['score'])
		else:
			setattr(student, 'final', userScore['score'])
		student.save()

# gets each student's name and huxley id
def getStudentData(headers):
	data_url = 'https://www.thehuxley.com/api/v1/quizzes/7852/users?max=100&offset=0'

	data_response = requests.get(data_url, headers=headers)

	students = []
	
	for students_data in data_response.json():
		students.append({
			'nome': students_data['name'].lower(),
			'id_huxley': students_data['id']
		})

	return students

# gets urls from [start, end)
def getScoreUrlsLists(start, end):
	urls = []
	
	for ids in range(start, end):
		urls.append('https://www.thehuxley.com/api/v1/quizzes/' + str(ids) + '/scores')

	return urls

def getScoreUrlsTests(ids_urls):
	urls = []
	
	for ids in ids_urls:
		urls.append('https://www.thehuxley.com/api/v1/quizzes/' + str(ids) + '/scores')

	return urls

def getUserScores(url, headers, type_score):
	userScores = []

	response = requests.get(url, headers=headers).json()
	for user in response:
		userScore = {}
		userScore['id_huxley'] = user['userId']

		score = 0
		for correctProblem in user['correctProblems']:
			if type_score == 1:
				score += correctProblem['score']
			else:
				score += round(correctProblem['partialScore'], 1)
		
		userScore['score'] = score

		userScores.append(userScore)

	return userScores

def get_token(username, password):
	headers = {
		"Content-type": "application/json"
	}
	data = {
		"username": username,
		"password": password
	}
	response = requests.post("https://thehuxley.com/api/login", headers=headers, data=json.dumps(data))
	token_json = response.json()
	return token_json["access_token"]

def getSubmission(access_token):
	headers = {"Authorization": "Bearer " + access_token}

	students = getStudentData(headers)
	setStudentDataOnDatabase(students)

	urls_lists = getScoreUrlsLists(7852, 7860)
	
	for index, url in enumerate(urls_lists):
		userScores = getUserScores(url, headers, 1)
		setStudentScoreListOnDatabase(userScores, index+1)

	urls_tests = getScoreUrlsTests([8043, 8048, 8049, 8050])

	for index, url in enumerate(urls_tests):
		userScores = getUserScores(url, headers, 2)
		setStudentScoreTestsOnDatabase(userScores, index+1)
	
	urls_tests_reassessments = getScoreUrlsTests([8057, 8058])

	for index, url in enumerate(urls_tests_reassessments):
		userScores = getUserScores(url, headers, 2)
		setStudentScoreTestsReassessmentsOnDatabase(userScores, index+1)


def updateGrade():

	while True:
		try:
			login = os.environ['HUXLEY_USER']
			password = os.environ['HUXLEY_PASS']
			token = get_token(login, password)

			getSubmission(token)
			calcularAB1()
			calcularAB2()

			print('Notas atualizadas por ultimo em: ', datetime.datetime.now(pytz.utc).strftime('%d/%m/%Y %H:%M:%S %Z %z'))
		except:
			print('Não conseguiu conectar')

@user_passes_test(lambda u: u.is_superuser)
def updateGradesThreading(request):
	gradesThread = threading.Thread(target=updateGrade)
	gradesThread.start()
	return redirect('resolution')
	

def index(request):
	return redirect('resolution')

def resolution(request):
	data = {}
	colunas = ('Nome', 'Turma', 'Prova 1', 
	'Lista 1', 'Lista 2', 'Prova 2', 'Lista 3',
	'Lista 4', 'Prova 3', 'Lista 5', 'Lista 6',
	'Prova 4', 'Lista 7', 'Lista 8')

	lista = []
	for i in Aluno.objects.all():
		i.nome = i.nome.title()
		lista.append(i)

	alunos_ordenados = sorted(lista, key = lambda x: x.nome)

	data['alunos'] = alunos_ordenados
	data['colunas'] = colunas

	return render(request, 'nota/resolution.html', data)

def notasAcumuladas(request):

	data = {}
	colunas = ('Nome', 'Turma', 'AB1', 'AB2', 
	'Reav', 'Final', 'Média', 'Situação',)

	lista = []
	for i in NotaAluno.objects.all():
		i.nome = i.nome.title()
		lista.append(i)

	alunos_ordenados = sorted(lista, key = lambda x: x.nome)

	data['alunos'] = alunos_ordenados
	data['colunas'] = colunas

	return render(request, 'nota/notas.html', data)

def calcularMedia(dados, index):
	aluno = NotaAluno.objects.get(nome = dados[0][index])
	
	if aluno.reav > aluno.ab2 and aluno.ab2 <= aluno.ab1:
		aluno.mediaFinal = round(((aluno.reav + aluno.ab1)/2), 2)
	elif aluno.reav > aluno.ab1 and aluno.ab1 <= aluno.ab2:
		aluno.mediaFinal = round(((aluno.reav + aluno.ab2)/2), 2)
	else:
		aluno.mediaFinal = round(((aluno.ab1 + aluno.ab2)/2), 2)

	if aluno.mediaFinal >= 7:
		aluno.situacao = 'APROVADO'
	elif aluno.mediaFinal < 5:
		aluno.situacao = 'REPROVADO'

	aluno.save()


def calcularFinal(dados, index):
	aluno = NotaAluno.objects.get(nome = dados[0][index])

	final = (((6 * aluno.mediaFinal) + (4 * aluno.final))/10)

	if final >= 5.50 or final > aluno.mediaFinal:
		aluno.mediaFinal = round( final, 2)
		if(final >= 5.50):
			aluno.situacao = 'APROVADO'
	else:
		aluno.situacao = 'REPROVADO'

	aluno.save()

def calcularMediaFinal(aluno):
	alunoF = NotaAluno.objects.get(id_huxley = aluno.id_huxley)
	alunoF.mediaFinal = round(((alunoF.ab1 + alunoF.ab2)/2), 2)
	alunoF.save()

def calcularAB1():
	alunos = Aluno.objects.all()

	for aluno in alunos:
		try:
			alunoF = NotaAluno.objects.get(id_huxley = aluno.id_huxley)
			alunoF.ab1 = round(((((aluno.prova1 + aluno.prova2)*7)/20) + (((aluno.lista1 + aluno.lista2 + aluno.lista3 + aluno.lista4)*3)/58)), 2)
			alunoF.save()
		except:
			notaAB1 = round(((((aluno.prova1 + aluno.prova2)*7)/20) + (((aluno.lista1 + aluno.lista2 + aluno.lista3 + aluno.lista4)*3)/58)), 2)
			alunoF = NotaAluno(nome = aluno.nome , id_huxley = aluno.id_huxley, ab1 = notaAB1)
			alunoF.save()

		calcularMediaFinal(aluno)
			
def calcularAB2():
	alunos = Aluno.objects.all()

	for aluno in alunos:
		try:
			alunoF = NotaAluno.objects.get(id_huxley = aluno.id_huxley)
			alunoF.ab2 = round(((((aluno.prova3 + aluno.prova4)*7)/20) + (((aluno.lista5 + aluno.lista6 + aluno.lista7 + aluno.lista8)*3)/66)), 2)
			alunoF.mediaFinal = round( ((alunoF.ab1 + alunoF.ab2)/2), 2)
			if alunoF.mediaFinal >= 7:
				alunoF.situacao = 'APROVADO'
			alunoF.save()
		except:
			notaAB2 = round(((((aluno.prova3 + aluno.prova4)*7)/20) + (((aluno.lista5 + aluno.lista6 + aluno.lista7 + aluno.lista8)*3)/66)), 2)
			alunoF = NotaAluno(nome = aluno.nome, id_huxley=aluno.id_huxley, ab2 = notaAB2)
			alunoF.mediaFinal = round( ((alunoF.ab1 + alunoF.ab2)/2), 2)
			if alunoF.mediaFinal >= 7:
				alunoF.situacao = 'APROVADO'
			alunoF.save()

def searchNotaIndividual(request):
	if request.method == 'POST':
		search = request.POST['search']

		if request.POST['select'] == 'nome':
			result_search = Aluno.objects.filter(nome__contains=str(search).lower())
		elif request.POST['select'] == 'turma':
			result_search = Aluno.objects.filter(turma=search.upper())

		dados = {}
		colunas = ('Nome', 'Turma', 'Prova 1', 
		'Lista 1', 'Lista 2', 'Prova 2', 'Lista 3',
		'Lista 4', 'Prova 3', 'Lista 5', 'Lista 6',
		'Prova 4', 'Lista 7', 'Lista 8')

		lista = []
		for i in result_search:
			i.nome = i.nome.title()
			lista.append(i)

		alunos_ordenados = sorted(lista, key = lambda x: x.nome)

		dados['alunos'] = alunos_ordenados
		dados['colunas'] = colunas
		
		return render(request, 'nota/resolution.html', dados)
	else:
		return redirect('resolution')
		
def searchNotaGeral(request):
	if request.method == 'POST':
		search = request.POST['search']

		if request.POST['select'] == 'nome':
			result_search = NotaAluno.objects.filter(nome__contains=str(search).lower())
		elif request.POST['select'] == 'turma':
			result_search = NotaAluno.objects.filter(turma=search.upper())

		dados = {}
		colunas = ('Nome', 'Turma', 'AB1', 'AB2', 
		'Reav', 'Final', 'Média', 'Situação',)

		lista = []
		for i in result_search:
			i.nome = i.nome.title()
			lista.append(i)

		alunos_ordenados = sorted(lista, key = lambda x: x.nome)

		dados['alunos'] = alunos_ordenados
		dados['colunas'] = colunas
		
		return render(request, 'nota/notas.html', dados)
	else:
		return redirect('notas')