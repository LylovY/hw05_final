from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Group, Post, Comment

User = get_user_model()


class PostFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)
        cls.guest_client = Client()

    def test_form_create_authorised_client(self):
        '''Проверяем, что форма create_post создает запись в БД'''
        posts_count = Post.objects.count()
        form_data = {
            'text': 'Тестовая запись',
            'group': self.group.id
        }
        self.authorised_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)

    def test_form_create_guest_client(self):
        """Страница по адресу /create/ перенаправит анонимного
        пользователя на страницу логина. Пост в БД не создастся
        """
        posts_count_before = Post.objects.count()
        form_data = {
            'text': 'Тестовая запись',
            'group': self.group.id
        }
        response = self.guest_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        posts_count_after = Post.objects.count()

        self.assertRedirects(
            response, '/auth/login/?next=/create/'
        )
        self.assertEqual(posts_count_before, posts_count_after)

    def test_form_post_edit_authorised_client_author(self):
        '''Проверяем, что при авторизованном авторе
         форма post_edit редактирует запись в БД'''
        post_for_edit = Post.objects.create(
            author=PostFormTest.user,
            text='Тестовый пост 2',
        )
        id_post = post_for_edit.id
        form_data = {
            'text': 'New',
            'group': self.group.id
        }
        self.authorised_client.post(
            reverse('posts:post_edit', kwargs={'post_id': id_post}),
            data=form_data,
        )
        post_for_edit = Post.objects.get(pk=id_post)
        self.assertEqual(post_for_edit.text, form_data['text'])
        self.assertEqual(post_for_edit.group.id, form_data['group'])

    def test_form_post_edit_authorised_client_nonauthor(self):
        '''Проверяем, что при авторизованном не авторе
         форма post_edit не редактирует запись в БД'''
        post_for_edit = Post.objects.create(
            author=PostFormTest.user,
            text='Тестовый пост 2',
        )
        id_post = post_for_edit.id
        form_data = {
            'text': 'New',
        }
        self.user2 = User.objects.create_user(username='Non_post_writer')
        self.authorised_client2 = Client()
        self.authorised_client2.force_login(self.user2)
        response = self.authorised_client2.post(
            reverse('posts:post_edit', kwargs={'post_id': id_post}),
            data=form_data,
        )
        post_for_edit = Post.objects.get(pk=id_post)
        self.assertNotEqual(post_for_edit.text, form_data['text'])
        self.assertRedirects(
            response, f'/posts/{id_post}/'
        )

    def test_form_post_edit_guest_client(self):
        """Страница по адресу /posts/<int:post_id>/edit/ перенаправит анонимного
        пользователя на страницу логина. Пост в БД не редактируется
        """
        post_for_edit = Post.objects.create(
            author=PostFormTest.user,
            text='Тестовый пост 2',
        )
        id_post = post_for_edit.id
        form_data = {
            'text': 'New',
            'group': self.group.id
        }
        response = self.guest_client.post(
            reverse('posts:post_edit', kwargs={'post_id': id_post}),
            data=form_data,
        )
        post_for_edit = Post.objects.get(pk=id_post)
        self.assertNotEqual(post_for_edit.text, form_data['text'])
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{id_post}/edit/'
        )


class PostCommentFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Post_writer')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)
        cls.guest_client = Client()

    def test_create_only_authorized_user(self):
        '''Комментировать посты может только авторизованный пользователь'''
        comment_count_before = Comment.objects.count()
        id_post = PostCommentFormTest.post.id
        form_data = {
            'text': 'New',
        }
        self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': id_post}),
            data=form_data,
        )
        comment_count_after = Comment.objects.count()
        self.assertEqual(comment_count_before, comment_count_after)
        self.authorised_client.post(
            reverse('posts:add_comment', kwargs={'post_id': id_post}),
            data=form_data,
        )
        comment_count_after = Comment.objects.count()
        self.assertEqual(comment_count_before + 1, comment_count_after)
