from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from .forms import RegisterForm
from django.urls import reverse

def index(request):
    template = loader.get_template('PyClass/index.html')
    context = {}
    return HttpResponse(template.render(context, request))

def dashboard(request):
    return HttpResponse("Личный кабинет")

def loginpage(request):
    return HttpResponse("Логин")

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save(commit = True)
            return HttpResponseRedirect(reverse('pyclass:dashboard'))
    else:
        form = RegisterForm()
    return render(request, 'PyClass/register.html', {'form': form})