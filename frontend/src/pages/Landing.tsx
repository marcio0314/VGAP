import { Navigate } from 'react-router-dom'

export default function Landing() {
    // Authentication disabled - redirect directly to app
    return <Navigate to="/app" replace />
}
