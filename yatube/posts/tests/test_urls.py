from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ..models import Group, Post

User = get_user_model()


class PostURLTest(TestCase):
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
            text='Тестовая пост',
        )
        cls.authorised_client = Client()
        cls.authorised_client.force_login(cls.user)
        cls.guest_client = Client()

    def test_url_exists_at_desired_location(self):
        """Страницы  доступны любому пользователю."""
        status_ok = HTTPStatus.OK.value
        templates_url_names = {
            '/': status_ok,
            '/group/test-slug/': status_ok,
            '/profile/Post_writer/': status_ok,
            f'/posts/{PostURLTest.post.id}/': status_ok,
        }
        for address, code in templates_url_names.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address)
                self.assertEqual(response.status_code, code)

    def test_post_edit_url_exists_at_desired_location_authorised_author(self):
        """Страница /posts/<post_id>/edit/ доступна
         авторизованному пользователю-автору."""
        response = self.authorised_client.get(
            f'/posts/{PostURLTest.post.id}/edit/')
        self.assertEqual(response.status_code, HTTPStatus.OK.value)
        # авторизованный пользователь(не автор),
        # будет перенаправлен на страницу поста
        self.user_non_author = User.objects.create_user(username='Non_author')
        self.authorized_client2 = Client()
        self.authorized_client2.force_login(self.user_non_author)
        response = self.authorized_client2.get(
            f'/posts/{PostURLTest.post.id}/edit/', follow=True)
        self.assertRedirects(
            response, f'/posts/{PostURLTest.post.id}/'
        )

    def test_create_url_exists_at_desired_location_authorised(self):
        """Страница /create/ доступна авторизованному пользователю."""
        response = self.authorised_client.get('/create/')
        self.assertEqual(response.status_code, HTTPStatus.OK.value)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        # Шаблоны по адресам
        templates_url_names = {
            '/': 'posts/index.html',
            '/group/test-slug/': 'posts/group_list.html',
            '/profile/Post_writer/': 'posts/profile.html',
            f'/posts/{PostURLTest.post.id}/': 'posts/post_detail.html',
            f'/posts/{PostURLTest.post.id}/edit/': 'posts/create_post.html',
            '/create/': 'posts/create_post.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorised_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_unexisting_page(self):
        '''Запрос к несуществующей странице вернёт ошибку 404'''
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND.value)
