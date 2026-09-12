import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import { AuthOptions } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string; // Your *database's* user ID
      email: string;
      name: string;
      image?: string;
      apiToken: string; // Backend authentication token
    };
  }
}

// The Server-Side Encrypted Token (what's in the HttpOnly cookie)
declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    email: string;
    name: string;
    image?: string;
    apiToken: string; // Your backend's token is stored *here*, safely.
  }
}

// A helper type for the `account` object during signIn
declare module "next-auth" {
  interface Account {
    backendToken?: {
      access_token: string;
      user: {
        id: string;
        email: string;
        name: string;
        image?: string;
      };
    };
  }
}

const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    }),
  ],

  // We must use the "jwt" strategy for this pattern
  session: {
    strategy: "jwt",
  },

  callbacks: {
    /**
     * 2. SIGNIN CALLBACK
     * This runs ONCE at login.
     * It sends the Google `id_token` to your backend for verification.
     */
    async signIn({ account }) {
      if (account?.provider === "google" && account.id_token) {
        try {
          // SECURE: Send the Google ID Token to your backend
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
          const response = await fetch(
            `${backendUrl}/users/auth/google`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${account.id_token}`,
              },
              body: JSON.stringify({}),
            },
          );

          if (!response.ok) {
            console.error("Backend auth failed:", response.statusText);
            return false; // Abort login
          }

          // Your backend returns its *own* token and user data
          // We attach this to the `account` object to pass it to the `jwt` callback
          account.backendToken = await response.json();
          return true;
        } catch (error) {
          console.error("Error in signIn callback:", error);
          return false;
        }
      }
      return true;
    },

    /**
     * 3. JWT CALLBACK
     * This runs every time a session is read or updated.
     * The `token` object is encrypted and stored in the secure HttpOnly cookie.
     */
    async jwt({ token, account }) {
      // On the first sign-in, `account.backendToken` will exist.
      if (account && account.backendToken) {
        // SECURE: Store your backend's token and user ID in the
        // encrypted cookie.
        token.id = account.backendToken.user.id;
        token.email = account.backendToken.user.email;
        token.name = account.backendToken.user.name;
        token.image = account.backendToken.user.image;
        token.apiToken = account.backendToken.access_token;
      }
      return token;
    },

    /**
     * 4. SESSION CALLBACK
     * This creates the *client-side* session object (what `useSession()` sees).
     */
    async session({ session, token }) {
      // Pass the non-sensitive user data to the client
      session.user.id = token.id;
      session.user.email = token.email;
      session.user.name = token.name;
      session.user.image = token.image;
      session.user.apiToken = token.apiToken;

      // Console log the session data
      console.log("Session User ID:", session.user.id);
      console.log("Session User Email:", session.user.email);
      console.log("Session User Name:", session.user.name);
      console.log("Session API Token:", session.user.apiToken);

      return session;
    },

    async redirect({ url }: { url: string }): Promise<string> {
      if (url.includes("/api/auth/callback/google")) {
        return `${process.env.NEXTAUTH_URL}/datastore/browse`;
      }
      if (url.startsWith("/")) {
        return `${process.env.NEXTAUTH_URL}${url}`;
      }
      return url.startsWith(process.env.NEXTAUTH_URL!)
        ? url
        : process.env.NEXTAUTH_URL!;
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };
