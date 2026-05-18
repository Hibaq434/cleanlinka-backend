from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .serializers import (
    RegisterSerializer, VerifyOTPSerializer,
    ResendOTPSerializer, LoginSerializer, UserSerializer,
    LogoutSerializer, NINVerificationSerializer
)
from .models import OTPVerification, NINVerification
from .utils import send_otp

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        send_otp(user, channel='SMS')
        return Response({
            'message': 'Registration successful. OTP sent via SMS.',
            'phone_number': user.phone_number,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    serializer = VerifyOTPSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        otp = OTPVerification.objects.filter(
            user=user,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).last()

        if not otp:
            return Response(
                {'error': 'Invalid or expired OTP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save()
        user.is_active = True
        user.is_verified = True
        user.save()

        tokens = get_tokens_for_user(user)
        return Response({
            'message': 'Account verified successfully.',
            'tokens': tokens,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    serializer = ResendOTPSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.is_active:
            return Response(
                {'error': 'Account already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )

        send_otp(user, channel='SMS')
        return Response(
            {'message': 'OTP resent via SMS.'},
            status=status.HTTP_200_OK
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {'error': 'Account not verified. Please verify your OTP.'},
                status=status.HTTP_403_FORBIDDEN
            )

        tokens = get_tokens_for_user(user)
        return Response({
            'message': 'Login successful.',
            'tokens': tokens,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    serializer = LogoutSerializer(data=request.data)
    if serializer.is_valid():
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
            return Response(
                {'message': 'Logged out successfully.'},
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {'error': 'Invalid or expired token'},
                status=status.HTTP_400_BAD_REQUEST
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_nin(request):
    serializer = NINVerificationSerializer(data=request.data)
    if serializer.is_valid():
        nin = serializer.validated_data['nin']

        existing = NINVerification.objects.filter(user=request.user).first()
        if existing:
            if existing.status == 'VERIFIED':
                return Response(
                    {'error': 'NIN already verified'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            existing.nin = nin
            existing.status = 'PENDING'
            existing.save()
            return Response({
                'message': 'NIN updated and submitted for verification.',
                'status': 'PENDING'
            }, status=status.HTTP_200_OK)

        NINVerification.objects.create(
            user=request.user,
            nin=nin
        )
        return Response({
            'message': 'NIN submitted for verification.',
            'status': 'PENDING'
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])

def get_dev_otp(request):
    if not settings.DEBUG:
        return Response(
            {'error': 'This endpoint is only available in development'},
            status=status.HTTP_403_FORBIDDEN
        )

    phone_number = request.query_params.get('phone_number')
    if not phone_number:
        return Response(
            {'error': 'phone_number is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    otp = OTPVerification.objects.filter(
        user__phone_number=phone_number,
        is_used=False
    ).last()

    if not otp:
        return Response(
            {'error': 'No active OTP found'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'otp': otp.code,
        'expires_at': otp.expires_at,
        'phone_number': phone_number
    }, status=status.HTTP_200_OK)