from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm, PostForm
from .models import Follow, Group, Post, User

PAGE_PER_LIST = 10


def paginator(request, post_list, page_per_list):
    paginator = Paginator(post_list, page_per_list)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def index(request):
    template = 'posts/index.html'
    title = 'Последние обновления на сайте'
    post_list = Post.objects.select_related('author', 'group').all()
    page_obj = paginator(request, post_list, PAGE_PER_LIST)
    context = {
        'title': title,
        'page_obj': page_obj
    }
    return render(request, template, context)


def group_posts(request, slug):
    template = 'posts/group_list.html'
    group = get_object_or_404(Group, slug=slug)
    post_list = group.posts.select_related('author', 'group').all()
    page_obj = paginator(request, post_list, PAGE_PER_LIST)
    context = {
        'title': group.title,
        'group': group,
        'page_obj': page_obj
    }
    return render(request, template, context)


def profile(request, username):
    template = 'posts/profile.html'
    following = False
    self_follow = False
    title = f'Профайл пользователя {username}'
    author = get_object_or_404(User, username=username)
    fio = author.get_full_name
    post_author = author.posts.select_related('author', 'group').all()
    count = post_author.count()
    page_obj = paginator(request, post_author, PAGE_PER_LIST)
    if request.user.is_authenticated:
        if request.user == author:
            self_follow = True
        if Follow.objects.filter(user=request.user).exists():
            authors_follow = Follow.objects.values(
                'author_id').filter(user=request.user).all()
            list_id = [id['author_id'] for id in authors_follow]
            if author.id in list_id:
                following = True
    context = {
        'title': title,
        'author': author,
        'post_author': post_author,
        'page_obj': page_obj,
        'fio': fio,
        'count': count,
        'following': following,
        'self_follow': self_follow
    }
    return render(request, template, context)


def post_detail(request, post_id):
    template = 'posts/post_detail.html'
    post = get_object_or_404(Post, id=post_id)
    count = Post.objects.filter(author=post.author).count()
    title = 'Детали поста'
    form = CommentForm()
    post_comments = post.comments.select_related('post', 'author').all()
    context = {
        'post': post,
        'count': count,
        'title': title,
        'form': form,
        'comments': post_comments,
    }
    return render(request, template, context)


@login_required
def post_create(request):
    template = 'posts/create_post.html'
    title = 'Новый пост'
    form = PostForm()
    context = {
        'form': form,
        'title': title,
        'is_edit': False
    }
    if request.method == 'POST':
        form = PostForm(request.POST, files=request.FILES or None)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('posts:profile', request.user)
        return render(request, template, context)
    return render(request, template, context)


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user != post.author:
        return redirect('posts:post_detail', post_id=post.id)
    form = PostForm(instance=post)
    if request.method == 'POST':
        form = PostForm(
            request.POST,
            files=request.FILES or None,
            instance=post)
        if form.is_valid():
            form.save()
        return redirect('posts:post_detail', post_id=post.id)
    template = 'posts/create_post.html'
    context = {
        'form': form,
        'is_edit': True,
        'post_id': post.id
    }
    return render(request, template, context)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('posts:post_detail', post_id=post_id)


@login_required
def follow_index(request):
    title = 'Избранные авторы'
    post_list = Post.objects.select_related(
        'author').filter(author__following__user=request.user)
    page_obj = paginator(request, post_list, PAGE_PER_LIST)
    context = {
        'title': title,
        'page_obj': page_obj
    }
    return render(request, 'posts/follow.html', context)


@login_required
def profile_follow(request, username):
    author = User.objects.filter(username=username).get()
    if not Follow.objects.filter(
            user=request.user, author=author).exists(
    ) and author != request.user:
        Follow.objects.create(
            user=request.user,
            author=author
        )
    return redirect('posts:profile', username=username)


@login_required
def profile_unfollow(request, username):
    author = User.objects.filter(username=username).get()
    Follow.objects.filter(author=author).delete()
    return redirect('posts:profile', username=username)
